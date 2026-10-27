# 从纯 SV 项目逐步迁移到 SVX

[English](README.md)

> 入门教程草案：本小型项目不作为项目级端到端验收依据。用户要求改用具有现成
> SV 验证环境的更大项目；本目录的未完成验收项见文末，不能视为全部通过。

本教程从一个**能独立编译运行的纯 SystemVerilog 验证项目**出发，保持 DUT、
时钟、复位、driver 和 monitor 不变，分三次改造，把事务、场景和检查策略移到
Python。四个目录是可运行的检查点，不是必须顺序覆盖同一目录的补丁。
它是一个完整的小型寄存器项目，不依赖商业 IP 或 UVM，也不声称覆盖全部 SVX API。

先阅读[共享运行指南](../RUNNING_EXAMPLES.zh-CN.md)。需要综合学习继承、handle、
信号诊断等其他能力时，再运行[寄存器小项目](../register_lab/README.zh-CN.md)。
这里不为展示 API 而改造不需要改造的边界。

## 改造的目标与不变量

硬件包含四个 32 位寄存器，地址为 `0/4/8/12`，复位值均为零。总线采用
`valid/ready/write/address/wdata/rdata`，地址决定 0、1 或 2 个等待周期。
这不是完整的标准总线协议实现。一次传输仅在 `posedge clk` 且 `valid && ready`
时接受；请求在负边沿驱动。读数据在接受边沿前已稳定，monitor 不依赖延时猜测
NBA 完成，也不从 driver 的 response 中复制 observation。

默认程序有 64 笔事务：先读四个复位值，再写四个寄存器，随后交替读写与覆盖。
每一笔都有唯一 tag。验证同时检查 response 和独立采样的 observation。

| 检查点 | 场景与事务产生 | response 检查 | monitor scoreboard | 预期 |
|---|---|---|---|---|
| [00_sv](00_sv/tb.sv) | SV | SV | SV | 无 SVX/SvTypes 依赖的基线 |
| [01_entry](01_entry/tb.sv) | SV | SV | SV | 只验证 Python 启动和退出 |
| [02_stimulus](02_stimulus/tb.sv) | Python/SvTypes | Python | SV | 窄的 typed request/response 边界 |
| [03_python](03_python/tb.sv) | Python/SvTypes | Python | Python | 场景和检查都在 Python，pin 行为仍在 SV |

四个版本复用 [DUT](common/dut.sv)、[硬件及复位](common/harness.svh)和
[driver/monitor](common/environment.svh)。因此不会用“Python 版 driver”替换原来的
时序实现，也不会为迁移后的版本另写一个行为不同的 DUT。

## 构建与运行约定

从仓库根目录操作。保留现有工程的编译、库加载和日志保存流程，逐次将顶层源文件
替换为表中的 `tb.sv`；每个检查点使用独立构建目录。不要一次编译四个 `tb`。

| 阶段 | 额外构建输入 |
|---|---|
| `00_sv` | 仅项目根 include 路径，不加载 SVX 原生库 |
| `01_entry` | SVX 的 SV 源码 include 路径与原生 DPI 库；Python 能导入本项目 |
| `02_stimulus`、`03_python` | 同上，再加 SvTypes SV 运行时 include 路径和生成的模型 |

这些顶层文件已 `include` 所需源码，不要再将 `svx_pkg.sv`、DUT 或生成模型重复
作为独立编译单元加入。各库路径和编译参数的获取方式见共享运行指南。

```sh
# 已安装 SVX/SvTypes 时，保留项目根供嵌入式 Python 导入 examples。
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
python -m examples.project_migration.generate
python -m examples.project_migration.generate --check
svx sv-files
svx compile-flags
svx libs
```

源码开发时，把 `python` 和 `../svtypes/python` 放在额外 site-packages **之前**。
不要只设置启动 pytest 的路径，却忘记把相同路径传给仿真器中的 Python。
这个项目只使用通道，不要求启用层次信号访问，也不需要 inheritance manifest。

将各次运行的输出分别保存为 `run/00_sv.log` 等文件。除最后一节的新用例外，
四阶段均使用默认入口和相同 64 笔程序，不需要 plusarg。

## 第一步：先证明纯 SV 项目本来就正确

`00_sv/tb.sv` 同时启动五个有限任务：

```systemverilog
fork
  driver();
  monitor();
  legacy_sequence();
  legacy_responses();
  legacy_scoreboard();
join
check_complete();
report_complete();
```

原始类型在 `common/legacy_types.svh`。SV sequence 用 mailbox 交给 driver，
monitor 仅采样 DUT 引脚，两个检查器分别维护从零初始化的参考寄存器。
不要在接入 SVX 时顺手修正协议、重写 BFM 或更换采样边沿，否则无法区分迁移
问题和原工程行为变化。

基线必须先得到：

```text
MIGRATION_SV_RESPONSES_PASS count=64
MIGRATION_SV_SCOREBOARD_PASS count=64
MIGRATION_PROJECT_PASS count=64 observations=64 waits=48
```

用独立的日志验收工具检查所有数据和接受时刻，而不是只搜索 PASS：

```sh
python -m examples.project_migration.verify run/00_sv.log --stage 00_sv
```

第一笔接受于 35 ns，最后一笔接受于 1775 ns；共经历 48 个等待周期。
`verify.py` 只依赖 Python 标准库；在尚未安装 SVX 时也可直接作为脚本运行。

## 第二步：只接入运行时，不改验证行为

`01_entry/tb.sv` 相对基线的实质变化是：

```diff
+ `include "sv/svx_pkg.sv"
+ import svx_pkg::*;
+ svx_init();
+ svx_run_test("examples.project_migration.scenarios", "entry");
  fork /* 原有五个 SV 任务 */ join
  check_complete();
+ svx_shutdown();
  report_complete();
```

`scenarios.py::entry` 是普通同步 Python 函数，只输出
`MIGRATION_PY_ENTRY_PASS`。不启动 Python 时钟，不引入 `asyncio`，也不创建 host
thread。这一步若失败，只调查库加载、Python 导入、入口或生命周期，不调查事务编码。

```sh
python -m examples.project_migration.verify run/01_entry.log --stage 01_entry \
  --baseline run/00_sv.log
```

除了入口标记，64 笔数据、顺序及采样时刻必须与纯 SV 基线完全相同。

## 第三步：迁移场景，保留原 SV scoreboard

在 `models.py` 中定义与原记录对应的三个 SvTypes 类型。例如：

```python
@svobj(registry=package)
class MigrationRequest(SvObject):
    tag = Int()
    stop = Bit[1]()
    write = Bit[1]()
    address = Bit[8]()
    data = Bit[32]()
```

`generate.py` 通过公开 `svx svtypes-gen --channel-helpers` 生成 SV class 和
typed helper。`02_stimulus/tb.sv` **替换**旧类型的 include，不是同时编译同名
新旧类。Python 是跨语言数据契约的唯一来源；不要另写一套字节布局或手工打包 response。

在原 mailbox 边界加入 `common/typed_boundary.svh` 的 adapter：

```systemverilog
svx_get_MigrationRequest("migration.bus.req", request);
requests.put(request); // 原 driver 不变。

responses.get(response);
svx_put_MigrationResponse("migration.bus.rsp", response);
```

入口的变化是：

```diff
- legacy_sequence();
- legacy_responses();
+ request_bridge();
+ response_bridge();
+ svx_run_test("examples.project_migration.scenarios", "stimulus");
  legacy_scoreboard();
```

Python 用 `svx.reqrsp_channel("migration.bus", MigrationRequest, MigrationResponse)`
发送 `request_for(op)`，检查 `bus.request(...)` 返回的 response。普通 Python
`Operation` 只是本地场景计划；真正经过边界的对象始终是 SvTypes 事务。
SV 的独立 monitor 和 scoreboard 继续工作，这使本阶段能同时验证新链路和旧检查器。

```sh
python -m examples.project_migration.verify run/02_stimulus.log --stage 02_stimulus \
  --baseline run/00_sv.log
```

应新增 `MIGRATION_PY_RESPONSES_PASS count=64`，仍保留
`MIGRATION_SV_SCOREBOARD_PASS count=64`，完整总线轨迹保持不变。

## 第四步：迁移独立检查，完成 Python 主导的项目

`03_python/tb.sv` 最后替换一个检查边界：

```diff
- legacy_scoreboard();
- svx_run_test("examples.project_migration.scenarios", "stimulus");
+ monitor_bridge();
+ svx_run_test(python_module, python_test); // 默认 smoke。
```

monitor 将自己采样到的 `MigrationObservation` 放入 `migration.bus.mon`。
`scenarios.py::run_program` 中，producer 和 observer 是两个由仿真器调度的同步
Python 进程：

```python
svx.fork_join([producer, observer])
```

producer 检查 response；observer 独立检查 tag、操作、地址、数据和条数。预期结果
在并发前从场景计算为不可变 tuple，因此 observer 即使先运行，也不依赖 producer
尚未填入的共享字典。不要以“response 正确”代替对实际总线活动的观察。

```sh
python -m examples.project_migration.verify run/03_python.log --stage 03_python \
  --baseline run/00_sv.log
```

最终应有 `MIGRATION_PY_SCOREBOARD_PASS count=64 addresses=4 operations=2`、
Python response 通过标记和项目完成标记，不再启动旧 SV sequence 或 scoreboard。

### 收尾是协议的一部分，不依赖固定事务数量

`stop=1` 是明确的 typed 结束记录，不驱动 DUT：

1. producer 发送最后一个 request 后，再发送 stop 并等待 response 结束确认。
2. driver 排空当前传输、撤销 valid，再设置 `driver_done` 并确认结束。
3. monitor 完成采样循环，在 observation 流发送自己的结束记录。
4. observer 消费该记录，Python fork/join 返回；SV 所有 bridge 和 BFM join 完成。
5. 检查 `driven == sampled` 后才 shutdown，最后输出项目 PASS。

不能用“Python 函数已返回”或“收到了最后一个 response”推断 monitor 已结束。
正常退出不需要用 kill 掩盖阻塞进程，也不能让每个 SV bridge 写死 `repeat(64)`。
`stop` 只负责这个小项目的单 producer 有限流；多 producer 项目需要定义自己的
排空/汇合规则，不能把第一个 producer 的 stop 当成所有生产者完成。

## 证明只修改 Python 就能扩展用例

用**同一个 `03_python` 二进制**加 `+MIGRATION_TEST=stress`，运行 4096 笔请求。
这超过通道默认容量 1024，用来检验并发消费和有限结束协议，而不是性能测试。

```sh
python -m examples.project_migration.verify run/stress.log --stage 03_python \
  --count 4096 --salt 0x12345678
```

随后在 Python 导入路径中新建 `runtime_added_migration_case.py`：

```python
import svx
from examples.project_migration.scenarios import program, run_program

@svx.test
def newly_added():
    run_program(program(192, salt=0xdeadbeef))
```

不重新生成模型、不编译 SV、不替换原生库，使用
`+MIGRATION_MODULE=runtime_added_migration_case +MIGRATION_TEST=newly_added` 启动。

```sh
python -m examples.project_migration.verify run/newly_added.log --stage 03_python \
  --count 192 --salt 0xdeadbeef
```

最后再次运行默认 smoke，证明原用例仍可用。新增场景、数据、检查算法只改 Python；
修改 SvTypes 字段或 SV 协议边界则必须重新生成并编译。改了 Python 不等于所有
修改都能跳过构建输入检查；这里没有跨语言继承声明，因而没有相应的 manifest 步骤。

## 检查器也必须接受验证

对四个版本分别加 `+MIGRATION_CORRUPT_READ`：DUT 读数据低位被翻转，第一笔
复位读就应失败。再对纯 SV 和最终版本分别加
`+MIGRATION_CORRUPT_OBSERVATION`：只破坏 tag 8 的 monitor 记录，driver response
保持正确，必须由 monitor scoreboard 捕获。

```sh
python -m examples.project_migration.verify run/bad_monitor.log --stage 03_python \
  --expect-error MIGRATION_MONITOR_MISMATCH
```

| 故障位置 | 允许的明确诊断 |
|---|---|
| 纯 SV / 入口版 DUT 读数据 | `MIGRATION_SV_RESPONSE_MISMATCH` 或 `MIGRATION_SV_MONITOR_MISMATCH` |
| 事务迁移版 DUT 读数据 | `MIGRATION_RESPONSE_MISMATCH` 或 `MIGRATION_SV_MONITOR_MISMATCH` |
| 最终版 DUT 读数据 | `MIGRATION_RESPONSE_MISMATCH` 或 `MIGRATION_MONITOR_MISMATCH` |
| 独立 monitor 记录 | 对应 SV/Python 的 `MIGRATION_*MONITOR_MISMATCH` |

双检查器并发时不规定谁先报错。必须有对应的 checker 诊断、fatal、且没有项目
PASS；超时、崩溃、导入失败或任意非零退出状态都不算“成功发现故障”。进程状态也
可能不足以判定 fatal，必须检查日志内容。

## 应保留到实际项目的工作方式

- **先建立不变量，再缩小改动面。** 固定 DUT/时序层，用逐事务和逐时刻轨迹证明
  正常路径没有变化；故障验证独立执行，不混入正常通过标准。
- **按请求、响应、观察分流。** driver 的 response 和独立 monitor 的 observation
  不是同一份证据。生产和消费并发，避免大用例积压或靠增大队列掩盖收尾问题。
- **数据声明只有一个跨语言来源。** 模型生成由一个入口维护；`--check` 只读验收，
  过期时先重生成，不手改生成文件。只是迁移事务时，不引入对象镜像或直接 pin 访问。
- **按仿真语义采样。** 本协议在接受边沿前已有稳定读数据；其他协议若在 NBA
  更新响应，需要定义对应的 clocking/采样规则，不能照抄本例或添加任意 `#0`。
- **显式结束每条流。** PASS 只在请求、响应、观察、Python 任务和 SV BFM 全部完成
  后输出。UVM 工程保留原 phase/objection/factory，入口集成另见 Cookbook 第 7.1 节。

## 已完成的端到端验证

2026-10-24 的实际进度如下；不是最终验收记录：

| 验收项 | 结果 |
|---|---|
| 四阶段默认 64 笔程序 | 数据、顺序和所有接受时刻与纯 SV 基线一致；每次 48 个等待周期 |
| 最终版 4096 笔 stress | 未通过验收；旧版长用例出现大量换页，已停止，事务对象生命周期待修正 |
| 编译后新增 Python module/用例 | 尚未执行 |
| 再运行原 smoke | 尚未执行最终复核 |
| 四阶段 DUT 读数据故障 | 四次均由指定检查器诊断终止，无项目 PASS |
| 纯 SV / 最终版 monitor 独立故障 | 两次均由 monitor 检查器捕获 |
| 转换前 X/Z 检查 | 已补源码，新增故障场景尚未远端复核 |

上述已通过结果来自补充 X/Z 检查之前的源码。当前新增检查及完整路线仍待复核。
不能据此推断更大项目、所有继承组合或所有协议已被覆盖，也不能将内存压力的原因
未经独立验证就归结为 SVX 核心缺陷。后续项目级验收将使用真实外部项目的原始 SV
验证环境；本例仅保留为分阶段接入的入门材料。
