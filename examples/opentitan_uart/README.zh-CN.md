# 将 OpenTitan UART 验证环境迁移到 SVX

[English](README.md)

共享环境与 runtime 加载说明见[示例运行指南](../RUNNING_EXAMPLES.zh-CN.md)。

本项目从真实 OpenTitan UART 验证环境开始，不重新实现 UART 驱动。两种模式共用
原 RTL、接口、agent、寄存器模型与虚拟 sequencer，差别在于上层逻辑的归属。

| 层次 | 混合模式 | Python 主导模式 |
| --- | --- | --- |
| UART/TL 引脚时序、driver、monitor | 原 SV | 原 SV |
| UART 初始化、寄存器访问服务 | 原 SV | 原 SV |
| 场景组织 | 原 SV sequence body | Python `body()` |
| TX 事务生成 | 原 SV `process_tx()` | Python `process_tx()` |
| RX 事务生成、读回检查 | Python | Python |
| 字节流模型、帧检查 | Python 与原 SV checker 双跑 | Python，关闭原 UART 数据 checker |
| 协议与安全断言 | 保留 | 保留 |

Python 主导模式的用例算法与期望数据均在 Python，但本例**没有**声称替换上游
scoreboard 全部的 CSR、中断、超时、错误预测和覆盖率模型。原有 SV 用例仍应保留。

## 1. 先取得未修改项目的基线

固定 OpenTitan commit：`724f378edf920eb5bc536a0d136158963c44186b`。
按照其安装指南准备依赖，将上游工作区与 SVX 分开保存。原配置为
`hw/ip/uart/dv/uart_sim_cfg.hjson`。
可从[固定版本的 UART DV 源码](https://github.com/lowRISC/opentitan/tree/724f378edf920eb5bc536a0d136158963c44186b/hw/ip/uart/dv)
查看环境与 sequence；原 driver/monitor/item 位于上游 `hw/dv/sv/uart_agent`。

先通过上游自己的 DVSim 入口运行原环境：

```sh
dvsim hw/ip/uart/dv/uart_sim_cfg.hjson \
  -i uart_smoke uart_tx_rx uart_fifo_full uart_fifo_overflow \
     uart_fifo_reset uart_rx_parity_err uart_loopback uart_intr \
  --fixed-seed 1 --max-parallel 1
```

不为通过基线而关闭 assertion 或 scoreboard。记录源码版本、原构建命令、二进制
身份、用例、seed 与 UVM 严重级别汇总；之后每一步都以这份基线为参照。

## 2. 选择小而真实的类边界

新增 [`uart_bridge.sv`](uart_bridge.sv)，其中 `UartSequence extends uart_smoke_vseq`。
实际初始化、约束、sequencer 行为和事务服务都来自上游。新增方法只负责暴露
寄存器读回结果和独立监视记录，不另建 UART agent。

让原构建系统在调用编译器时，把实际工作目录与完整 argv 导出为
`compiler-input.json`（对象只有 `directory` 与 `arguments` 两个成员，argv 首项
是编译器）。这样无需重列 UVM、UART 环境和 RTL 的依赖、宏与 include 路径：

```sh
svx compile-config --sv-build-command "$UART_BUILD_COMMAND"
svx export --class uart_svx_bridge_pkg::UartSequence \
  --member body process_tx process_rx uart_init dut_shutdown \
    spinwait_txidle spinwait_rxidle send_tx_byte send_rx_byte read_rx \
    observed_count observed_item parity_enabled parity_odd \
    item_data item_frame item_identity same_item make_item set_item_data \
  --sv-build-command "$UART_BUILD_COMMAND" \
  --sv-source examples/opentitan_uart/uart_bridge.sv --out "$UART_GENERATED"
```

CLI 从源码自动发现这20个方法的签名和完整11层祖先，包括已经求值的原生类
类型参数；无需 declarations JSON，也无需人为添加 Python target。
只有 UartSequence 是导出目标，import 和原生 class handle 不会请求导出整个 UVM。
只读检查重复同一条 export 命令并加 `--check`。保留原编译器环境，以便找到其隐式 UVM
库。输入与支持边界见[编译配置导入](../../docs/SVX_BUILD_INPUTS.md)。这里验证
已选接口的依赖上下文，不意味着将全部上游类自动选为生成目标。

[`generate.py`](generate.py) 保留显式维护的契约快照，便于未准备上游源码时查看
本例的接口。它复用同一生成后端，但直接源码导出不需要该脚本。快照与源码发现
的输出不要混用同一个生成目录。

原命令若包含 `-y` / `+libext+`，无需先展开目录。SVX 保留其搜索顺序，按缺失
单元名选择具体文件；未选文件不会进入解析或依赖记录。导出检查仍用同一条命令。
追加验证同时对照了实际编译器的库选择，并在带库搜索的完整 UART 构建中重新
运行两种迁移模式，见[验收记录](RESULTS.zh-CN.md)。

在原工程的编译清单中，将 [tb_migration.sv](tb_migration.sv) 放在上游 UART 环境 package 之后。
include 路径加入 SVX 仓库根目录、SvTypes runtime 目录和 `$UART_GENERATED`；在原
顶层模块之外增加 `uart_svx_migration_registration`。该源码先包含 bridge，再包含
生成的 `mirrors.sv`。按 [用户手册](../../docs/SVX_USER_MANUAL.md) 构建并加载匹配的
SVX native runtime。
采用上面的直接源码导出命令时，在该 top 的 `svx_init()` 之后、`svx_load()` 之前
调用 CLI 报告的 `svx_exports_pkg::initialize()`，显式注册生成的 factory 和 dispatcher。

也可在同一 export 命令中增加 `--integrated`，生成包含桥接的源码副本。此时按
`artifacts.json` 的 `source_replacements` 和 `systemverilog_compile_order` 替换原
编译输入；先编译 SvTypes/SVX runtime package，不要再同时编译原清单或单独的
bridge/mirrors。在迁移 top 中移除开头的四条重复 include，保留其 test package 和
registration module，并使用同一个 initialize 调用。仍保留原工程的隐式库选项和
DPI 链接设置，不能因为副本含有库源码文本就删除这些选项。此模式已重新编译并
验证 mixed、Python 主导和原 SV 三条路径，见[验收记录](RESULTS.zh-CN.md)。

必须保留原构建的访问权限、断言、语言和插桩选项。扩展原构建，不手工重组全部
RTL 清单；迁移构建使用独立输出目录，不覆盖原基线二进制。

生成的公开 Python 类型名为 `svx_mirror.uart_svx_bridge_pkg.UartSequence`。
运行时将生成的 Python 目录和本示例目录加入 `PYTHONPATH`，将
`SVX_ARTIFACT_MANIFEST` 指向生成的 `artifacts.json`。

## 3. 导出真实事务，而非脱离 SV 的字典

`UartCapture` 独立订阅原 monitor 的 TX/RX analysis port，不抢占原 scoreboard
的 FIFO。每次 `write()` 克隆原生 `uart_item`：生产者可能复用或修改原对象，检查器
需要自己拥有的稳定快照。

`observed_item(tx, index)` 返回该原生快照的
`RemoteRef["sv://uart_agent_pkg/uart_item"]`。本例有意把此类作为 opaque handle：
通过 `UartSequence` 的生成接口 `item_data`、`item_frame`、`item_identity` 读取成员，
不是宣称 opaque handle 能自动访问任意属性。

```python
item = sequence.observed_item(1, index)
assert sequence.same_item(item, sequence.observed_item(1, index))
data = sequence.item_data(item)
```

创建门禁还会调用 `make_item()`，通过 `set_item_data()` 修改真正 SV 对象的成员，
验证 native identity 不变。快照与身份是两件事：克隆是为了固定观测；反复导出
同一快照时必须保留其身份。handle 属于当前 session，shutdown 后不可继续使用。

## 4. 先迁移一侧

运行参数选择 `+UVM_TESTNAME=UartMigrationTest`、`+en_scb=1`，并设置仿真进程
环境变量 `UART_MIGRATION_MODE=mixed`。

唯一的 SV test adapter 处理 UVM 配置和 sequencer 交接。Python 创建 `PythonUart`
并发布对象，SV 通过 `SVX_GET_OBJECT` 得到真正的原生基类 handle。用户方法不需要
处理 request/response 打包。

仍需保留原生 UVM 生命周期：

```systemverilog
configure_sequence(sequence_handle);
if (!sequence_handle.randomize()) `uvm_fatal("UART_RANDOMIZE", "native constraints failed")
sequence_handle.start(env.virtual_sequencer);
```

构造对象不等于已经绑定 sequencer/configuration。Python `__init__` 只准备本地
模型，不在正常 UVM 交接之前启动依赖配置的总线活动。

```python
def body(self):
    if self.mode == "mixed":
        super().body()
```

原 SV body 继续组织两轮 TX/RX 并发；TX 事务生成仍在 SV，RX 生成与读回迁到
Python。两个方向均经过 `send_*_byte` 虚方法 hook，Python 先记录意图，再通过
`super()` 调原 SV 实现。此阶段原 SV checker 与 Python checker 双跑。

host 保持 UVM objection，直到 Python 检查完成；随后关闭配对对象、清理 SVX，
最后才 drop objection。不把清理代码放在原 `run_test()` 之后，因为它可能直接
结束仿真而不返回。

## 5. 迁移场景与检查责任

保留**同一个二进制和生成契约**，改为 `UART_MIGRATION_MODE=python`，并选择
`+en_scb=0`。

```python
for _ in range(2):
    self.uart_init()
    svx.fork_join([self.process_tx, self.process_rx])
    self.dut_shutdown()
```

Python 自行组织场景，共生成 64 个 TX 与 64 个 RX 字节，包括全零、全一、交替位
模式，并检查 64 次寄存器读回。CSR 访问、UART 引脚时序和 idle 等待仍由原生 SV
方法执行；Python 不逐位驱动，不使用异步事件循环。TX 写后的 1us 延迟是本场景的
显式稳定等待，不是通用采样屏障，也不能代替协议同步。

不要以为关闭 scoreboard 后，原 helper 就自动独立了。上游 idle helper 首先读取
`ctrl.get_mirrored_value()`，其预测者恰好是该 scoreboard。因此 `UartSequence`
覆写 idle 服务，改为带超时地轮询真实 CSR 响应。否则短场景可能只是恰好没有
填满 FIFO，扩大后就丢包；Python checker 必须报告观测缺失，不能接受变短的流。

[`model.py`](model.py) 独立持有 TX/RX 期望流，根据**独立 monitor 的观测**检查数据、
数量、顺序、start/stop 位及启用的 parity；不读取原 scoreboard 的私有队列或预测
状态。RX 寄存器读回还与 Python 意图逐笔比较。本例在用例结束时比较流，不是
无限长运行的无损日志服务。

两种模式共用一个 SV host，不为每个 Python 场景生成 SV test。本例以既有 SV test
名承载 Python 算法，不另建 Python UVM factory。运行时注册 Python 用例名的功能
见 [Cookbook 的 UVMX 章节](../../docs/SVX_COOKBOOK.zh-CN.md)。对应仅源码提供的示例为
仓库内 `incubator/uvmx/examples/peer_test_selection`，不随核心示例打包。

## 6. 证明检查器确实能失败

观测 tap 提供三个显式负向控制：

| 参数 | 观测注入 | 预期 Python 诊断 |
| --- | --- | --- |
| `+UART_SVX_CORRUPT_TX` | 损坏捕获的 TX 数据 | `UART_MODEL_STREAM TX` |
| `+UART_SVX_DROP_TX` | 丢弃首个 TX 事务 | `UART_MODEL_STREAM TX` |
| `+UART_SVX_REORDER_TX` | 调换首两个 TX 事务 | `UART_MODEL_STREAM TX` |

在 Python 主导模式、`+en_scb=0` 下运行；必须经 SVX 正常 fatal 策略终止，且不得
输出 `UART_MIGRATION_PASS` 或 `TEST PASSED CHECKS`。故障注入位于 monitor 之后，
不是修改 DUT RTL，其目的就是证明 Python 检查器真正承担检查责任。

再用 `+UVM_TESTNAME=uart_base_test`、原 `+UVM_TEST_SEQ` 和 `+en_scb=1` 运行保留的
SV 用例；这一路径不初始化 Python。

## 7. 不重编译地新增 Python 用例

[`all_bytes_case.py`](all_bytes_case.py) 定义 `Test(PythonUart)`，每轮遍历全部
256 个字节值，TX/RX 顺序相反，两轮共检查 512 TX、512 RX 和 512 次读回。
[`rotated_bytes_case.py`](rotated_bytes_case.py) 是另一个独立扩展模块，使用两种
不同的全字节排列。

```python
from uart_migration import PythonUart

class Test(PythonUart):
    def tx_pattern(self):
        return tuple((index * 73 + 19) & 255 for index in range(256))
```

设置 `UART_MIGRATION_CASE_MODULE=rotated_bytes_case`、`UART_MIGRATION_MODE=python`，
沿用相同 UVM host 和 `+en_scb=0`。入口导入该模块的 `Test`，通过同一 SVX mirror
构造真正的 Python 子类，不增加 SV 类、virtual slot、manifest target 或生成桥接。
完成构建后，只增加 Python 源码即可加入此类用例。这个选择器属于本项目，不等于
注册新的 `+UVM_TESTNAME`。

只读检查现有生成契约时，重复第2节的 export 命令并加 --check，保持原工程输入一致。

## 验证与迭代

验收摘要见 [RESULTS.zh-CN.md](RESULTS.zh-CN.md)。分清原项目故障、生成故障、
native/类桥接故障和 Python 模型错误；保留完整 UVM 汇总与原异常，不只看进程
退出码。

首次构建后，只修改 Python 方法体或模型只需启动新的仿真进程；修改被选中方法的
签名、SV helper、类契约或生成代码则需要重新生成/编译。用二进制、native library
及生成文件的哈希验证复用，不能仅凭“这次跑得很快”判断没有重编译。

OpenTitan 是独立的 Apache-2.0 项目。本目录只提供 SVX 接入代码，不复制整份上游
RTL/DV；分发派生源码或补丁时保留其许可证和声明。
