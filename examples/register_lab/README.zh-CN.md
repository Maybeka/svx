# 寄存器验证小项目

[English](README.md)

这是项目式 Cookbook 的四寄存器外设：事务闭环、进程、双向继承、字段、handle、
信号诊断及回调都使用同一个 DUT。正常流程与故障用例分开，核心项目不依赖 UVM。

## 当前验证流程

`models.py` 使用 SvTypes 定义请求、响应和观察事务，`generate.py` 生成 SV 模型
与通道辅助任务。`tb.sv` 管理时钟、复位、真实的 `dut.sv`、driver 和独立采样的
monitor。`scenarios.py` 并发运行 Python producer 和 scoreboard，两者共享预期值表。

正常用例写入四个寄存器，再逐个读回：共八个请求、八个响应、八个独立观察。
后台 watchdog 展示 kill 时的清理；短竞赛展示 join-any 和停止剩余进程。
层次访问仅用于 cookie/status 诊断以及单独的故障注入，不承担密集总线访问。

## 生成与编译

在仓库根目录、已安装匹配 SVX/SvTypes 的 Python 环境中执行：

```sh
python -m examples.register_lab.generate
python -m examples.register_lab.generate --check
svx sv-files
svx compile-flags
svx libs
```

编译 `examples/register_lab/tb.sv`，它已包含 DUT、interface、生成模型和支持包。
将仓库根目录与 SvTypes 的 SV 运行时目录加入 include 路径，加载匹配的 SVX
原生库。仿真器内嵌 Python 的导入路径应包含项目根与安装包目录。
本项目需要原生库和仿真构建启用直接层次信号访问，环境操作见
[共享运行指南](../RUNNING_EXAMPLES.zh-CN.md)。

生成流程包括 SvTypes 事务、Python/SV 源码发现、inheritance manifest、镜像/代理、
受限 VIF view、artifact manifest 和 callback-only Report。需要 `pyslang` 与 SVX
运行依赖；嵌入 Python 必须能导入它们。除了安装包或开发源码路径，仿真进程还需要：

```sh
export PYTHONPATH="$PWD/examples/register_lab/generated/python:$PWD:${PYTHONPATH:-}"
export SVX_ARTIFACT_MANIFEST="$PWD/examples/register_lab/generated/svx-artifacts.json"
```

源码开发另加 `python` 和 `../svtypes/python`。`--check` 只检查，不修复；输入或输出
过期时重新运行不带 `--check` 的生成命令。不要手工改 `generated/` 内的代码。

## 用例与判定

- 默认或 `+LAB_CASE=smoke`：依次输出 `REGISTER_LAB_SIGNALS_PASS`、
  `REGISTER_LAB_PROCESSES_PASS`、`REGISTER_LAB_BUS_PASS transactions=8 observations=8`、
  `REGISTER_LAB_PAYLOAD_PASS`、`REGISTER_LAB_PYTHON_PASS`，最终输出
  `REGISTER_LAB_PASS case=smoke`，且没有错误诊断。
- `+LAB_CASE=corrupt_read`：将总线读数据 force 为零。scoreboard 必须报告
  `REGISTER_LAB_MISMATCH`，随后按 SVX fatal 策略结束，不得出现最终通过标记。
  不能仅凭进程退出码为零就认为这个负面用例通过。
- `+LAB_CASE=function_wait`：function 回调内故意执行 `svx.delay()`；必须在推进
  时间前拒绝，诊断包含 `svx.delay() is not allowed`、`Checker#compare` 和
  `SVX FATAL`，不得正常返回或出现最终通过标记。

正常流程还必须出现 `REGISTER_LAB_POLICY_CREATED`、`REGISTER_LAB_SV_CALLBACK_PASS`、
`REGISTER_LAB_HANDLES_PASS`、`REGISTER_LAB_CHECKER_PASS`、`REGISTER_LAB_POLICY_CLOSE_PASS`、
`REGISTER_LAB_REPORT_FUNCTION_PASS` 和 `REGISTER_LAB_REPORT_TASK_PASS`。
负面用例也要拒绝超时或崩溃，不能把任意失败当作预期失败。

进程检查之后还应出现 `REGISTER_LAB_INDEPENDENT_WAITS_PASS`：它验证独立通道
上的 get/peek 等待不互相干扰，peek 不消费数据。短竞赛必须只完成快进程，
慢进程由 `kill_running()` 清理，不能提前正常返回。

正常的密集访问留在时钟化 SV 代码中。Python 只通过 SVX 推进仿真时间，不使用
线程、async 或宿主机 sleep。

## 文件职责

| 文件 | 职责 |
|---|---|
| `dut.sv`、`register_if.sv` | 外设与总线连接 |
| `tb.sv` | 生命周期、时钟复位、driver、monitor、trace echo |
| `models.py`、`generated/models.sv` | 唯一类型化事务契约 |
| `scenarios.py` | 场景、scoreboard、进程与 payload 检查 |
| `signals.py` | 初始化时校验的声明路径 |
| `generate.py` | 生成与检查构建输入 |
| `policy_types.sv`、`extensions.py` | SV 基类、Python 派生策略、方向参数、外部 handle |
| `checker.sv`、`extensions.py::Checker` | SV 派生 Python checker、function/task 与 super |
| `reporting.py`、`generated/report.sv` | 公开 callback adapter 的 function/task 集成 |

## 按项目学习

1. 从 `models.py`、`register_if.sv` 和 `dut.sv` 看唯一数据契约与真实硬件。
   四个 32-bit 寄存器使用地址 0/4/8/12。
2. 阅读 `tb.sv` 的 initial，确认复位、声明信号校验、factory 注册、Python 入口
   和 shutdown 的顺序。所有时间与 SV 进程仍由仿真器调度。
3. 看 `check_processes` 与 `check_independent_waits`，再看 `check_bus`。
   producer 和 scoreboard 的预期表是共享 Python 对象，调用栈则相互独立。
4. driver 在边沿驱动并等数据稳定，monitor 独立采样；请求/响应与观察数据不能
   互相冒充。`lab.env.done` 收集 driver、monitor、trace 完成，避免最后响应后过早退出。
5. 再沿下面两个继承路径读代码，最后阅读信号诊断、raw trace 和 Report 回调。

### Python 派生 SV

`RegisterPolicyStub` 是空发现声明。生成器从 `policy_types.sv` 找到 SV 基类，
artifact manifest 让它绑定正式的 `svx_mirror.register_policy_pkg.RegisterPolicy`。
`PythonPolicy(mask)` 为自己创建配对的 SV 实例，用户不分配 object ID。

Python producer 和 SV driver 都调用 `normalize`。SV 持有 `RegisterPolicy` 基类
句柄，虚调用进入 Python override；`super().normalize(...)` 回到 SV 基类。
`mask`、`calls`、`history` 驻留 SV，Python 新声明的 SvTypes `local_checks` 在这个
target 中留在 Python。标量使用 `.value`，Queue 用 `history.push_back(...)`。
最终两端共调用 16 次，history 必须为 1 到 16；close 后 SV 字段不可再读，
Python 本地字段仍有效。

`calibrate` 在两侧各调用一次，展示 Input/Output/Inout：参数位置不改变，
Python 修改 carrier `.value`，普通结果单独返回；打包与 copy-out 都由 SVX 完成。
`word_bytes()` 展示静态方法。本项目通过实验性的 `publish_object` /
`SVX_GET_OBJECT` 显式交接已绑定对象，不是反射查找，也不转移所有权。

### SV 派生 Python

Python 源类 `Checker` 定义比较逻辑。SV 的 `RegisterChecker` 派生自生成的
`svx_proxy_extensions::Checker`。testbench 注册
`CheckerFactory#(RegisterChecker)`，Python 创建
`svx_py.examples.register_lab.extensions.Checker(42)` 时选择该 SV 实现。
这是单一实现选择，不替代完整交替 lineage 的源码集成生成流程。

`checker.compare(...)` 经 SV override 的 `super.compare(...)` 回到 Python 基类。
`finish` 先在 SV 延时，再经 Python 基类 `svx.delay` 延时，始终是同步 task。
`Bit[1]` 生成 `bit [0:0]`，手写 override 必须匹配，不能换成裸 `bit`。

### handle 的访问边界

PacketTag 不在生成列表中，Python 只取得不透明 `RemoteRef`，可保留、传回并
保持身份，不能读取 `number`。VIF 来自静态类型 `register_if.diagnostics`，只暴露
`read_address()`、`read_rdata()` 和 `read_data()`，没有总线写操作。
把 view 传回 `same_bus(view)`，由 SV 原生比较确认仍是同一个 interface。
不要读取生成 view 的私有 ID。

## 修改与构建

- 改事务字段、方法原型、投影字段或 SV 声明：重新发现、生成并编译 SV。
- 只改 Python 方法体：仍执行 `generate --check`，必要时刷新输入记录；桥接内容
  未改变时不必重编同一 SV，见[增量工作流](../../docs/SVX_USER_MANUAL.md#21-iterative-development)。
- 改事务数量：同步更新 driver/monitor 的次数与 checker 预期。
- `tests/python/test_register_lab_generation.py` 在隔离输出中验证删除生成文件后
  `--check` 失败且不修复，重新生成可恢复；它也确保 PacketTag 不会被额外生成成镜像。

## 可选 UVM 启动

源码中的 `incubator/uvmx/examples/register_lab` 复用本项目，用同一 UVM factory 的
`+UVM_TESTNAME` 分别启动 Python 定义和 SV 定义的 Test；操作及预期结果见该目录的
中英文 README。该临时适配不随 SVX 包导出，不是核心项目依赖，也不承诺深层 UVM 映射。
