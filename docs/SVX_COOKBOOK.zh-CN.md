# SVX Cookbook：从运行时基础到跨语言验证

本 Cookbook 按能力的依赖顺序组织 SVX 上手路径。它不要求重构已有
SystemVerilog 验证环境：先建立一个由仿真器调度的 Python 入口，再逐步
加入 SvTypes 数据、通道、继承和层次信号访问。

建议先按下面的项目路线运行一个完整事务闭环，再按章节理解各个边界。
每一步都说明三件事：应放在 SystemVerilog 还是 Python、为何如此，以及
如何在本仓库的完整示例中验证。各专项示例有自己的 testbench 和生成输入，
不是把前一节的片段直接追加到同一文件；运行时使用对应 README 的完整工程。
可以依次学习各章，也可以按验证需求选择专项边界。

## 迁移路线：从纯 SV 到 Python 场景和检查

如果你已有 SV 验证项目，先走[OpenTitan UART 完整改造教程](../examples/opentitan_uart/README.zh-CN.md)：
从未经修改的原 SV 基线出发，逐步导出真实事务对象，验证混合模式与 Python 主导模式，
再通过独立检查器和故障注入确认迁移结果。不要直接把综合示例的最终架构照搬进项目。

希望先理解更小的事务边界时，可读[四寄存器迁移草稿](../examples/project_migration/README.zh-CN.md)。
它提供四个可独立编译的检查点，但不是上述真实项目的验收记录：

| 阶段 | 本次改动 | 必须保留的证据 |
|---|---|---|
| 纯 SV 基线 | 暂不使用 SVX | 64 笔响应及独立观察正确，48 个协议等待周期 |
| Python 入口 | 仅添加 init、同步入口与 shutdown | 完整总线数据、顺序和接受时刻不变 |
| Python 事务生成 | SvTypes 声明、typed request/response adapter | 原 SV monitor scoreboard 仍通过 |
| Python 独立检查 | observation channel 和同步 fork/join | 两条检查流都排空，所有 SV/Python 任务完成后 PASS |

教程包含每一步的关键 diff、实际源文件、生成检查命令和只依赖标准库的日志
验收工具；教程还定义了编译后新增 Python 用例而不修改二进制，以及 DUT/monitor
故障捕获的验收方法。当前小型项目仍有未完成项，详见其验证状态；它只用于入门，
不能替代具有现成 SV 环境的真实项目级验证。共同的 DUT、driver、monitor 和时钟/复位代码不变，避免
将协议重写、采样变化和跨语言接入混成一次改造。

这条路线刻意不使用继承或层次信号服务：事务边界已经足够时，不把硬件时序搬到
Python。完成迁移后，再按真实需求选用后面的专项能力。

## 项目路线：四寄存器外设

[寄存器小项目](../examples/register_lab/README.zh-CN.md)把主要能力放在同一
可运行工程中，而不是串联不相关片段。先完成第 1 节环境准备，再按项目 README
生成、编译并运行 `smoke`。SV driver 驱动真实 DUT，独立 monitor 采样；Python
维护预期值，检查四次写入和四次读回。正常总线访问不经过层次信号服务。

建议分五次读代码，每次都保留已通过的完整工程：

1. **事务闭环：** `models.py` → `dut.sv` / `register_if.sv` → `tb.sv` 的
   driver/monitor → `scenarios.py::check_bus`。先确认八个响应与八个观察。
2. **调度与退出：** 看 `check_processes`、`check_independent_waits` 和
   `lab.env.done`。Python 堆共享不等于调用栈共享；最后一个响应也不等于
   所有 SV 进程已退出。
3. **对象扩展：** 看 `extensions.py`、`policy_types.sv`、`checker.sv`，沿
   两个方向追踪虚调用、`super`、字段驻留和 handle 身份。不要先读生成桥接。
4. **诊断与集成：** 看 `signals.py`、raw trace 和 `reporting.py`。分别运行
   `corrupt_read`、`function_wait`，确认有指定错误且没有正常通过标记。
5. **维护构建：** 看 `generate.py`，运行生成与 `--check`。先发现声明再检查
   桥接；修改方法体也不能跳过来源检查。生成输出不要手工修补。

| 能力 | 项目入口 | 正常运行的检查点 | 继续阅读 |
|---|---|---|---|
| 初始化、测试入口、收尾 | `tb.sv` / `smoke` | `REGISTER_LAB_PASS case=smoke` | 第 2、8 节 |
| 同步延时、fork/join、kill、finally、共享堆 | `check_processes` | `REGISTER_LAB_PROCESSES_PASS` | 第 3 节 |
| 独立 get/peek 等待 | `check_independent_waits` | `REGISTER_LAB_INDEPENDENT_WAITS_PASS` | 第 5 节 |
| SvTypes 事务、SV helper、独立 monitor | `check_bus` / driver / monitor | `REGISTER_LAB_BUS_PASS transactions=8 observations=8` | 第 4、5、7 节 |
| SV 基类 → Python 派生、SV 虚调用、super、字段 | `PythonPolicy` | `REGISTER_LAB_SV_CALLBACK_PASS`、`REGISTER_LAB_POLICY_CLOSE_PASS` | 第 9.1 节 |
| Python 基类 → SV 派生、function/task | `Checker` / `RegisterChecker` | `REGISTER_LAB_CHECKER_PASS` | 第 9.2 节 |
| Input/Output/Inout、静态方法 | `calibrate` / `word_bytes` | `REGISTER_LAB_POLICY_CREATED`、`REGISTER_LAB_SV_CALLBACK_PASS` | 第 9.3 节 |
| 不透明 class handle、受限 VIF | `check_handles` | `REGISTER_LAB_HANDLES_PASS` | 第 9.4 节 |
| 路径声明、四态读写、force/release | `check_signals` | `REGISTER_LAB_SIGNALS_PASS` | 第 10 节 |
| bytes/payload、peek、非阻塞操作 | `check_raw_trace` | `REGISTER_LAB_PAYLOAD_PASS` | 第 6 节 |
| 无参数 function/task 回调 | `Report` | `REGISTER_LAB_REPORT_FUNCTION_PASS`、`REGISTER_LAB_REPORT_TASK_PASS` | 第 7 节 |
| 源码发现、正式 stub 绑定、生成物检查 | `generate.py` | `REGISTER_LAB_GENERATED`、`REGISTER_LAB_ARTIFACTS_CURRENT` | 第 11 节 |

这个项目覆盖采用路径，不枚举每一种类型和继承形状。参数化类、交替 lineage、
更深的容器与随机化/覆盖率规则继续查阅第 9 节引用及专项测试，不能由上述标记
推断所有组合都已在本项目使用。当前对象交接采用实验性的 `publish_object` /
`SVX_GET_OBJECT`；字段和方法传输仍使用正式 SvTypes 契约。

可选的临时 UVM 入口位于源码 `incubator/uvmx/examples/register_lab`，复用同一
工程并通过 `+UVM_TESTNAME` 选择 Python 或 SV Test。它不随 SVX 包导出；先完成
不依赖 UVM 的主路线，再按第 7.1 节及该目录的中英文指南运行。

## 0. 先记住三个设计规则

1. **SystemVerilog 拥有仿真。** 时钟、复位、`@`、`#`、driver、monitor、
   进程和 UVM phase 留在 SV。Python 不能用 `async`/`await`、线程或宿主机
   定时器产生仿真时间。
2. **SvTypes 拥有数据契约。** 跨语言的类型化参数、返回值、通道数据、继承
   调用和信号值都用 SvTypes descriptor 与字节编码；SVX 不另造一套类型系统。
3. **边界必须显式。** Python 可被 SV 调用的函数要注册；通道要有名称；继承
   方法和字段要写入 manifest；层次信号路径要在初始化前声明。

这三个规则决定了通常的职责分配：Python 写场景、构造事务和检查结果；SV
驱动接口、等待时钟和采样硬件行为。

## 1. 准备开发环境和运行库

先完成[示例运行指南](../examples/RUNNING_EXAMPLES.zh-CN.md)中的环境、
生成输入和原生库准备。该指南是源码开发的统一操作入口；安装发布包时改用
[发布安装说明](RELEASE_1.0.0.md#installation-model)。不要从不同文档拼出一套安装命令。

进入下一节前，确认三个结果：

1. 当前 Python 能导入 SVX、SvTypes 和项目模块。
2. `svx sv-files`、`svx libs` 返回本次构建实际采用的输入。
3. [基础启动示例](../examples/milestone_1_basic)能在仿真中完成，而不只是原生库编译成功。

安装、构建和仿真采用同一个 Python ABI；依赖版本与发布验收条件以
[发布契约](RELEASE_1.0.0.md)为准。以下章节只增加各项能力特有的代码与检查点。

## 2. 建立最小 SV -> Python 入口

运行时的最小生命周期是：SV 初始化解释器，加载 Python 模块，启动一个明确注册
的函数，然后由 SV 结束仿真。

Python：

```python
import svx

@svx.export
def main():
    svx.display("Python entry is running")
    svx.delay(1.5, "ns")
```

SystemVerilog：

```systemverilog
`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  initial begin
    svx_init();
    svx_load("verification.tests.smoke");
    svx_start("verification.tests.smoke.main");
    svx_shutdown();
    $finish;
  end
endmodule
```

`svx_load` 只导入模块；`svx_start` 执行已注册的全名。对于通常的测试函数，使用
`svx_run_test(module_name, function_name)` 更简洁，它会处理加载并执行
`@svx.test` 注册函数。

```python
@svx.test
def test_smoke():
    ...
```

```systemverilog
svx_init();
svx_run_test("verification.tests.smoke", "test_smoke");
svx_shutdown();
$finish;
```

**为何要显式注册：** 运行时只调用 `@svx.export` 或 `@svx.test` 注册的目标；它
不会根据任意 import path 做反射调用。这样调用面、错误名和构建输入都可检查。

**检查点：** 编译并运行
[基础启动示例](../examples/milestone_1_basic)。输出应显示 SV 侧时间在
`svx.delay(1.5, "ns")` 后推进。

## 3. 使用仿真器拥有的 Python 原语

Python 已在一个 SVX 执行上下文内时，以下原语通过 DPI 返回 SV，再由 SV 恢复
Python 调用，因此保持仿真调度语义：

```python
svx.display("message")
svx.delay(10, "ns")
group = svx.fork_join_none([worker_a, worker_b])
group.await_()
```

可选的 fork 形式及用途：

| API | 返回时机 | 后续操作 |
|---|---|---|
| `svx.fork_join(callables)` | 所有子调用结束 | 无 |
| `svx.fork_join_any(callables)` | 任一子调用结束 | 需要时对返回的 group 调用 `kill()` |
| `svx.fork_join_none(callables)` | 子调用已被 SV 调度 | 使用 `await_()` 或 `kill()` |

子调用共享 Python 对象堆，但每个调用具有独立的执行上下文。`kill()` 是 SVX
进程组的显式停止操作，不是 Python 线程取消；它会让 SVX 管理的等待解除，并使
相关 Python 调用以取消状态收敛。
它会等待子调用完成清理再返回。任意用户 SV task 不会自动获得取消能力；
如果子调用正在等待这种 task，`kill()` 必须等它返回或主动响应取消。
不能同步 kill 包含自身的进程组，也不要吞掉内部取消异常；资源清理放在
`finally` 中。丢弃 group 的 Python 引用不会停止其子调用。

不要这样做：

```python
# 错误：这不是 SVX 的仿真模型
async def test():
    await asyncio.sleep(1)
```

**检查点：** 依次运行 [fork/join 示例](../examples/milestone_1_fork) 和
[共享状态示例](../examples/milestone_1_shared_state)。前者展示 join、join_any、
join_none、`await_()` 和 `kill()`；后者证明共享的是 Python 对象而不是调用栈。

## 4. 先定义数据，再定义跨语言接口

类型化数据在 Python 中由 SvTypes 定义。例如：

```python
from svtypes import Bit, Int, SvObject, svobj

@svobj
class BusReq(SvObject):
    id = Int()
    addr = Bit(8)
    data = Bit(32)
    write = Bit(1)
```

生成对应的 SV 类与类型化通道辅助任务：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx svtypes-gen \
  --module verification.types \
  --types BusReq,BusRsp,BusObs \
  --channel-helpers \
  --out verification/generated/types_and_channels.sv
```

生成文件是构建输入，应提交，或作为确定性的构建步骤生成并用同一命令检查。它
使 Python、SV 与所有跨语言调用共享 SvTypes 的统一类型名、编码指纹和二进制
版本。

**检查点：** 先照
[类型化辅助任务示例](../examples/milestone_7_sv_typed_helpers) 的生成命令运行；
再阅读其 `generated/types_and_channels.sv`，可看到 `svx_get_<Type>` 和
`svx_put_<Type>` 的具体产物。

## 5. 首选类型化通道连接 Python 和 SV

为每个协议角色使用稳定的层级化名称：

```text
env.bus0.req
env.bus0.rsp
env.bus0.mon
```

Python 侧创建对象并将意图放入请求通道：

```python
import svx
from verification.types import BusReq, BusRsp, BusObs

@svx.test
def test_bus():
    req = BusReq()
    req.id.value = 1
    req.addr.value = 0x20
    req.data.value = 0x1234
    req.write.value = 1

    svx.channel("env.bus0.req").put(req)
    rsp = svx.channel("env.bus0.rsp").get(BusRsp)
    obs = svx.channel("env.bus0.mon").get(BusObs)
    assert rsp.id.value == req.id.value
    assert obs.addr.value == req.addr.value
```

SV 侧只替换事务边界，保留真正的时序行为：

```systemverilog
task automatic driver();
  BusReq req;
  BusRsp rsp;

  svx_get_BusReq("env.bus0.req", req);
  // 在这里执行 @(posedge clk)、握手和接口驱动。
  rsp = new();
  rsp.id = req.id;
  svx_put_BusRsp("env.bus0.rsp", rsp);
endtask
```

生成辅助任务会在 SV 侧验证 payload 的 SvTypes 元数据，并要求 `unpack` 正好消费
所有字节。Python 侧的 `get(ExpectedType)` 也执行同样的 descriptor 检查；错误
类型不会被静默解码。

需要常见 request/response 语义时，可以使用 `svx.reqrsp_channel`；仅发送观察
值时可以使用 `svx.mon_channel`。这只是 Python 端的人机工程封装，底层仍是具名
SvTypes 通道。

**检查点：** 运行
[类型化总线示例](../examples/milestone_7_sv_typed_helpers)。它同时运行已有风格的
SV driver、SV monitor 与一个 Python 测试，展示请求、响应、观察值和空通道
`try_get`。

## 6. 仅在确有需要时使用原始 payload 通道

原始通道适合 trace、外部二进制块或尚未定义 SvTypes 模型的数据：

```python
svx.channel("env.trace").put_payload(
    b"\x00\x01\x7f",
    kind="bytes",
    content_type="application/octet-stream",
)
```

SV 可以用稳定的低层 payload 任务接收：

```systemverilog
chandle payload;
svx_channel_get_payload("env.trace", payload);
// 读取 payload 元数据和字节后必须销毁其所有权。
svx_payload_destroy(payload);
```

不要把原始 payload 当作类型化事务的替代品。它没有 `BusReq` 之类对象带来的
schema 约束，应用代码必须自己定义 `kind`、类型名、内容类型和字节含义。特别是
`Channel.put()` 与 `Channel.get()` 是 SvTypes 编码/解码入口；原始字节必须使用
`put_payload()`、`get_payload()`、`peek_payload()` 或其 `try_` 形式。

**检查点：**
[原始 payload 示例](../examples/milestone_2_payload_channel) 演示 blocking、
`peek`、nonblocking `try_get`/`try_put`、元数据与 payload 销毁。若已有稳定的
SvTypes 模型，应回到第 5 步。

## 7. 接入既有 SV 或 UVM 环境

需要真实项目的源码、改造边界和逐阶段验收时，使用
[OpenTitan UART 迁移教程](../examples/opentitan_uart/README.zh-CN.md)：原 driver/monitor
保持不变，先双跑 SV/Python 检查器，再将场景与字节流模型交给 Python。它还保留
原 SV 事务流并验证两者并发工作，不要求一次性迁走整个环境。
下面是接入原则的概览，不是替代完整工程的片段拼接指南。

SVX 的推荐首个落点不是重写 testbench，而是在既有 driver 和 monitor 的事务
边界接通类型化通道或类方法：

1. 在已有 SV 初始化路径调用 `svx_init()`。
2. 与现有 driver/monitor 并发启动一个 `svx_run_test()` 或 `svx_start()`。
3. driver 从 `<env>.<agent>.req` 取得 SvTypes item，或由生成的类方法调用原事务
   服务，按原来的时钟和协议驱动。
4. monitor 仍在 SV 时钟边沿采样，通过独立的 observation 通道或 analysis 订阅者
   导出观测；不抢占原 checker 的事务消费者。
5. Python 创建 scenario、维护 expected 数据，并消费 response 与 observation。
6. 在 SV teardown 中调用 `svx_shutdown()`，再结束仿真。

一个典型 SV 调度形状：

```systemverilog
initial begin
  svx_init();
  fork
    svx_run_test("verification.tests.bus", "test_bus");
    existing_style_driver();
    existing_style_monitor();
  join
  svx_shutdown();
  $finish;
end
```

UVM 环境同样保留其 component hierarchy、phase、objection、sequencer 和 factory。
SVX 只用于窄的事务边界；不要把 `raise_objection`、时钟等待或 monitor sampling
搬到 Python。

迁移时有三个容易被简单 smoke 掩盖的点：

- **观察不是响应的副本。** monitor 保留 SV 引脚采样，Python 并发消费独立观察；
  在启动两个 Python 进程前准备好预期数据，避免 producer/observer 运行顺序竞争。
- **最后一笔 response 不是收尾完成。** 等待 BFM 和场景结束，再检查独立观测与
  期望数量。通道型边界可用 typed stop/ack；UART 类边界则使用原 sequence 的
  `start()`/idle 完成语义，不必额外发明一套结束协议。
- **失败也要验收。** 对 DUT 数据和 monitor 记录分别注入故障。允许并发检查器中
  任一明确的预期诊断先出现，但超时、崩溃、导入失败不能算作 checker 通过。

### 7.1 用同一 UVM factory 启动 Python 或 SV 用例

首次接入先读[准备和使用 UVMX](UVMX_GETTING_STARTED.zh-CN.md)：假设 SVX 已就绪，
从源码与路径、默认 Python Test、固定 SV 包、原生启动到结果检查走完最小路径。
默认 `uvm_pkg::uvm_test` 已内置，不需要运行 UVMX 基类注册生成器；自定义基类和
新增 SV 可见事务的生成步骤单独按需增加，不能当作所有用户的必选准备。

临时原型位于源码 `incubator/uvmx`。寄存器项目的可选入口位于
`incubator/uvmx/examples/register_lab`；它复用核心项目的数据、driver、monitor
和检查逻辑，不要求将既有 SV 用例改写成 Python。

Python 用例使用同步实例方法；事务、用例逻辑和新增状态仍在 Python：

```python
from uvmx import Test, uvm_test

@uvm_test(canonical_id="py://verification/Smoke", factory_name="python_smoke")
class Smoke(Test):
    def run_phase(self):
        from examples.register_lab.scenarios import smoke
        smoke()
```

首次构建按该示例的指南生成核心数据/继承契约，编译固定 UVMX 接入和已选择的
SV 基类。SV 顶层先调用 `uvmx_init(python_module)` 加载用户模块及其导入模块中的
全部用例声明，通过 SvTypes 注册记录将名称加入正常 UVM factory，注册全部完成
后才返回。随后工程直接调用原生 UVM `run_test()`，不使用 UVMX 启动包装器：

```systemverilog
initial begin
  uvmx_pkg::uvmx_init("my_tests");
  uvm_pkg::run_test();
end
```

两个调用必须顺序执行，不能放在相互竞争的独立 initial 中。初始化不扫描未导入
的 Python 文件，也不修改 `finish_on_completion`、解析替代用例名或结束仿真。
原生 UVM 默认会结束仿真，不能依赖 `run_test()` 后的代码清理；若工程自行配置
它返回，则由工程在退出前调用现有的 `svx_shutdown()`。该接口是 task，不能在
final 中调用。退出策略不由 UVMX 初始化接口接管。
用户 Test 的创建、绑定和回调直接复用 SVX 现有机制，不另设委托对象。
SV bridge 保持标准 `new(name, parent)` 构造签名，factory wrapper 在返回组件前
完成 Python 用例绑定和实例创建，不在 build_phase 中延后创建。
UVM 管理 phase 和 objection，Python `run_phase()` 返回后才结束该用例的 objection。

寄存器示例提供以下启动选择：

```text
+UVM_TESTNAME=register_lab_python_test
+UVM_TESTNAME=register_lab_extended_test
+UVM_TESTNAME=register_lab_sv_test
```

扩展用例 `PythonExtendedTest(PythonTest)` 增加 Python 状态和 `build_phase()`，
在 `run_phase()` 中调用 Python `super()` 复用原场景。除核心检查标记外，扩展
用例应输出 `REGISTER_LAB_UVMX_EXTENDED_BUILD_PASS` 和
`REGISTER_LAB_UVMX_EXTENDED_PASS`。

**新增用例不必重编 SV：** 在已加载模块内增加带 `@uvm_test` 的类，或在该模块
导入一个新 Python 用例模块；指定唯一 `factory_name`，并使用已编译的 `sv_base`
（默认 `uvm_pkg::uvm_test` 已内置）。重启同一个仿真程序并传入新名称，不再运行
生成器或 SV 编译器。新增 Python 字段、场景及受支持 phase 的重载同样不需重编。
这不是仿真运行中的热加载；新类必须在本次 UVM `run_test()` 前被导入。

新增未编译的 SV 基类，或更改 SV 实际消费的类型契约，仍需生成并编译相应 SV。
重复名称（包括与既有 SV 用例重名）会报错，不会覆盖。当前原型支持
`build_phase`、`connect_phase`、`end_of_elaboration_phase`、
`start_of_simulation_phase` 和 `run_phase`；构造无用户参数，前四个 function
phase 和构造禁止等待，run task 可使用同步 SVX 时序。它不提供完整 UVM 类体系映射。

### 7.2 仅需少量 Python 回调时

已有 SV 框架只需要调用几个无参数 Python 实例方法时，可用公开
`svx.callbacks.CallbackAdapter`，不必手写 DPI glue。寄存器项目的 `reporting.py`
声明 `completed` 为 function、`settle` 为 task；生成步骤用 `render_sv("Report")`
放入导入 `svx_pkg` 的 SV package。SV 初始化并加载模块后，Python 入口调用
`register_type(Report)`，SV 才执行 `new()` 与方法调用。
function 不能等待，task 保持同步、可使用 `svx.delay()`；参数、返回值、字段和
继承需求仍用继承生成器，不能硬塞进这个窄接口。完整契约见
[Callback 集成接口](SVX_API_REFERENCE.md#callback-integration-generator)。

**检查点：**
[既有环境示例](../examples/milestone_5_existing_env) 是可直接参照的完整小型
环境：SV 管理时钟、driver、monitor 和 memory，Python 管理四笔事务与检查策略。

## 8. 了解错误、上下文和关闭语义

所有会触达仿真器的 Python API 只能在 SVX 进入 Python 的动态调用范围内使用。
在普通 Python shell、pytest 或宿主线程中调用 `svx.delay`、通道、继承或信号 API
会抛出 `SVXContextError`，而不是偷偷创建宿主机行为。

默认异常策略是 `svx.FATAL`。发生未捕获异常时，SVX 保留 Python traceback，并由
SV 以 fatal 方式结束仿真。需要让调用者接收失败状态而不断言结束时，在 Python
入口前设置：

```python
import svx
svx.set_exception_policy(svx.REPORT)
```

`REPORT` 适用于导出的入口和进程子调用：它报告异常后继续，失败的子进程仍会在
等待时报告失败。生成的继承/构造回调失败始终 fatal，不会制造默认返回值。
上下文和通道 metadata 错误有专用 `SVXError` 子类；普通参数校验也可能抛出
`ValueError`、`TypeError` 或 `OverflowError`。

每次仿真收尾都遵守以下顺序：让已知 SVX 工作完成或显式 `kill()`，调用
`svx_shutdown()`，然后 `$finish`。关闭后保留的 channel、signal 或跨语言对象
引用是 stale。关闭是终态；不能在同一进程再次调用 `svx_init()`，下一次会话
需要新的仿真器进程。shutdown 会先取消并等待已跟踪的子调用，因此不响应
取消且尚未返回的用户 SV task 也会阻止关闭完成。

当前 shutdown 清理 SVX 注册表和 codec session，但嵌入式 Python 解释器仍
保留到仿真器进程退出，不会执行 CPython finalization。不要依赖解释器退出
钩子或对象垃圾回收来释放仿真资源，仍应显式 close、release 或在 `finally`
中清理。解释器保留到进程退出是有意的设计，不是尚未完成的 finalization
功能；shutdown 不承诺完整泄漏报告或强制任意用户 task 退栈。见
[所需能力与当前符合性](SVX_1_0_REQUIRED_FEATURES.md)。

**检查点：** [异常示例](../examples/milestone_1_error) 展示 fatal traceback；
关闭和失效规则可结合第 3 步进程组示例观察。

## 9. 需要面向对象扩展时，使用声明式跨语言继承

仅当扩展点本来就是一个稳定的类接口时使用跨语言继承。它不是任意对象反射：
方法、虚分派、参数、返回值、字段和继承链都需要出现在 manifest 中。

### 9.1 SV 基类由 Python 派生

适用情形：SV 已有 `virtual class BaseDriver`，希望 Python 编写某个 virtual
override。本示例由 Python 创建对象，再把对象交给 SV 基类句柄使用。

1. 写入完整 `BaseDriver(SV) -> PythonDriver(Python)` lineage 的 manifest。
2. 生成同名 Python mirror、SV bridge 和兼容性 artifact：

   ```sh
   PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
     --manifest examples/cross_language_inheritance/inheritance.json \
     --python-out examples/cross_language_inheritance/generated/python \
     --sv-out examples/cross_language_inheritance/generated/inheritance_mirrors.sv \
     --artifact-manifest examples/cross_language_inheritance/generated/svx-artifacts.json
   ```

3. 编译生成的 SV 文件，并让仿真进程可导入生成的 Python package。
4. Python 类继承生成的 `svx_mirror.<sv_package>.BaseDriver`，只重写 manifest 声明的 virtual
   方法；需要基实现时用通常的 `super()`。
5. 在导出的 Python 入口中实例化 Python 子类；生成的 mirror 创建并绑定 SV
   companion。使用示例中的实验性 `publish_object` / `SVX_GET_OBJECT` 交付接口，
   SV 获得基类句柄后调用其虚方法；不要在应用中手工构造内部 bridge。

若通过 Python declaration front end 编写 manifest，推荐直接从 Python 原型生成：

```python
import svx
from svtypes import Int

@svx.inheritance_method
def calculate(
    self,
    observed: svx.Output[Int],
    source: Int,
    changed: svx.Inout[Int],
) -> svx.Function[Int]:
    observed.value = changed.value
    changed.value += source
    return changed.value
```

未包裹的 `Int` 与 `svx.Input[Int]` 都表示 `input`；`Inout`、`Output` 和
`Function[Int]` 分别表达其方向、返回值和 function transport。每个参数独立标记，
一个方向标记不会影响后续参数。`-> svx.Task` 表达可消耗仿真时间的 task。
所有参数保持原有位置，`Output` 不要求末尾位置或默认值。SV 调用 Python 时，
SVX 为 output/inout 参数提供可变 carrier，用户读写其 `.value`；返回值只表示
普通 function 结果。request/response 的构造与编码由 SVX 完成，用户不接触它们。
未使用原型标注的既有代码仍可使用 `parameters=`、`return_type=` 和 `timing=`。

完整操作见 [SV 基类 -> Python 派生示例](../examples/cross_language_inheritance)。

### 9.2 Python 基类由 SV 派生

适用情形：Python 拥有 base 的构造和场景逻辑，SV 提供具体、与硬件紧密相关的
派生实现。

下面是当前可运行的 Python base + 单一 SV 实现的 factory 路径。它没有把
`SvCounter` 作为完整 lineage target 交给公开生成器，也不会自动发现或生成
`Python -> SV -> Python` 等交替链。普通独立 `--sv-out` 输出不能代替完整
源码布局；当前公开 CLI 的 `--sv-source` / `--sv-integrated-dir` 路径已支持
经过验证的 Python-root 交替链，也支持包含两类根的源码。必须提供完整
manifest 和有序源文件，编译生成的 `source.sv` 代替原始源码，不要同时编译
两份。详见[集成源码生成流程](SVX_USER_MANUAL.md#21-iterative-development)。
这不等于自动发现完整 lineage，也不证明任意交替形状或构造参数组合都可用。

独立 Python 源类及 SV-root 交替投影的静态 function/task 已可公开生成；
导入生成 Python 模块后无需创建源类实例。投影的静态回调按 manifest 中的
symbol 解析声明类，避免镜像与源类相互导入；同名派生方法不会改变声明类的
限定静态调用。源码集成生成路径支持多段继承中的自然构造参数计算：Python
初始化体只执行一次，在生成的镜像 `super().__init__(...)` 边界暂停，将已经
求值的参数交给对应 SV 基类的 `super.new(...)`；字段初始化与绑定完成后继续
执行。同一链的各段可有不同的参数列表，不需要扁平化签名或改写计算表达式。
下面的单一 factory 示例只演示实现选择；完整交替链应使用上述源码集成流程，
其顺序与验证范围见[构造参数路由](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md#constructor-routing)。

1. 在 manifest 中声明**Python base**、`constructor.initiator: "python"` 和全部
   crossing 方法。此方向的 manifest canonical class ID 是该 Python base，而不是
   应用 SV 派生类的名字。
2. 用同一 `inheritance-gen` 命令生成 `svx_proxy_<python_module>::BaseMonitor` 和 Python/SV adapter。
3. 用户在 SV 中定义具体派生类，让它继承生成的 Proxy，并把生成 Proxy 的
   构造参数由类型化 factory 传给自己的 `new`：

   ```systemverilog
   class SvCounter extends svx_proxy_base_monitor::BaseMonitor;
     function new(longint unsigned object_id, int seed);
       super.new(object_id);
       // 保存应用自己的构造状态。
     endfunction
   endclass
   ```

4. 在 `svx_init()` 后、Python 创建 base 前，创建生成的类型化 factory：

   ```systemverilog
   svx_proxy_base_monitor::BaseMonitorFactory#(SvCounter) factory;
   factory = new();
   ```

   factory 自动解码构造参数、以 Python base 的 ID 注册实现，并创建
   `SvCounter(object_id, seed)`。用户不实现内部 factory 接口，不解码 request，
   不操作 registry；派生类只把 SVX 提供的 opaque object ID 传给 `super.new`。
5. Python 创建生成的 Python base view；SVX 分配唯一 object ID，调用已注册的
   factory 创建并绑定 SV companion。随后 Python 调用会分派至 SV override，SV
   可以用 `super()` 回到 Python base。

完整操作见 [Python 基类 -> SV 派生示例](../examples/python_owned_inheritance)。

### 9.3 必须遵守的边界

- 只支持单继承、线性 lineage；多继承、mixin、字段遮蔽、未声明成员和方法重载
  会在生成期拒绝。
- `virtual` 方法用于跨边界动态分派。非 virtual 和静态方法仍可按 manifest
  包装调用，但不会改变 SV 的正常静态分派。当前公开生成器支持 SV 源静态
  方法，以及独立 Python 源 Proxy 和 SV-root 交替投影的静态 function/task。
  完整 Python-root 交替链使用前述源码集成生成流程，不能用单一 factory 示例
  代替完整 lineage 声明与源码输入。
- `input`、`output`、`inout` 和返回值使用 SvTypes response；`ref` 与
  `const ref` 跨继承边界不支持。
- 不支持把任意已经存在的 SV handle 接管为镜像。每个跨语言对象都必须由生成的
  构造器或 factory 创建，才能保证 object ID、生命周期和字段驻留一致。
- 若把 Python 声明的 SvTypes 字段投影给后续 SV 派生类，需要
  `svtypes.external-field-storage.v1`；只有最终投影目标中的字段驻留在 SV。
- 同一 receiver/method 的同步回调循环会被检测并拒绝，避免两个语言互相等待。

生成后将 `SVX_ARTIFACT_MANIFEST` 指向 artifact manifest；在 build gate 中运行
同一命令加 `--check`，拒绝过期生成物。

### 9.4 传递外部 class handle 与 virtual interface

不是每个跨边界的 SV handle 都应成为跨语言继承 target。对于仅需要传递、保存或
返回的任意 SV class，使用 `svtypes.RemoteRef[target]` 加
`svx.sv_class_handle(target, static_sv_type)` 声明静态类型。Python 得到的是不透明
引用：可以保存、传给兼容形参和返回，但不能构造对象、读取字段或调用方法。

virtual interface 同样使用 `RemoteRef`，但要用
`svx.virtual_interface_handle(target, "virtual if_name.modport")` 声明。生成 manifest
和 mirrors 时附加接口源码：

```sh
python -m svx inheritance-manifest \
  --python-module verification.python_api \
  --sv-source rtl/bus_if.sv \
  --out build/inheritance.json
python -m svx inheritance-gen \
  --manifest build/inheritance.json \
  --sv-source rtl/bus_if.sv \
  --python-out build/python \
  --sv-out build/mirrors.sv
```

生成器根据 interface/modport 自动产生受限 Python view，例如
`svx_vif.bus_if.master.Master`。它仅包含该静态 modport 可见的信号读写和
task/function；所有值仍使用 SvTypes 类型。不要为 VIF 维护第二份成员白名单，
也不要把 VIF 当作全局按名查找的资源。

**检查点：** [外部 handle 示例](../examples/foreign_handles) 同时验证派生 SV
class 经基类 handle 的身份保持、Python VIF 信号写入/function 调用，以及 VIF
回到 SV 后继续使用。

### 9.5 同包或交替继承的源码生成

同一 SV 包内既有基类又有后续派生类时，不需要拆包或手工插入桥接 include。
完成 manifest 发现后，用公开命令生成集成源码副本：

```sh
python -m svx inheritance-gen \
  --manifest inheritance.json \
  --sv-source bus_if.sv --sv-source drivers.sv --sv-compilation-unit \
  --python-out generated/python --sv-integrated-dir generated/sv \
  --artifact-manifest generated/svx-artifacts.json
```

构建时用 `generated/sv/source.sv` 替换列出的原 SV 源码输入，不能同时编译两份。
SvTypes 和 SVX 核心包仍先编译。原文件不被修改；生成器安置辅助类、共享记录
及公开类型别名。多文件按列出顺序解析，必须加 `--sv-compilation-unit`，并提供
实际构建使用的宏和 include 路径；源码解析需要安装 `manifest` extra。
同一命令增加 `--check` 检查新鲜度。重复生成不改未变化文件的时间戳，输出清单
和源码覆盖保护仍生效。声明变化仍先更新 manifest，不能用此命令替代发现阶段。
它与 `--sv-stage-dir`、`--sv-out` 互斥；任意源码宏形状和构造路由并非都已支持。
详细边界见[用户手册](SVX_USER_MANUAL.md)和[继承链契约](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md)。

## 10. 使用层次信号访问做小规模诊断

层次信号访问的目的只是配置检查、短暂观察和 fault injection。高频驱动、采样、
memory/queue 操作和批量访问仍应留在 SV。

先创建声明模块；每个可能使用的路径都要在这里给出 SvTypes codec：

```python
# verification/signal_declarations.py
import svx
from svtypes import Bit, Int, Logic, LongInt

ready = svx.declare_signal("tb.ready", Bit(1))
data = svx.declare_signal("tb.data", Bit(32))
status = svx.declare_signal("tb.status", Logic(8))
count = svx.declare_signal("tb.count", Int())
wide_count = svx.declare_signal("tb.wide_count", LongInt())
```

在普通 Python test 或 export 前，从 SV 启动声明验证：

```systemverilog
initial begin
  svx_init_with_signal_declarations("verification.signal_declarations");
  svx_run_test("verification.signal_test", "test_signals");
  svx_shutdown();
  $finish;
end
```

Python 测试内可在当前仿真调度点执行同步操作：

```python
from svtypes import LogicValue
from verification.signal_declarations import data, status

assert data.read() == 0
data.write(0x12)
data.force(0xa5)
try:
    svx.delay(1, "ns")
    assert data.read() == 0xa5
finally:
    data.release()
status.write(LogicValue.from_string("10xz01z0"))
```

初始化会一次性解析并验证所有路径的 VPI 对象类别、宽度和 signedness。`Bit` 等
两态 codec 读取到 `X/Z` 时会失败，绝不偷偷压缩为 0/1；`Logic` 使用
`LogicValue` 保存 value、X、Z 三个平面。force 不依赖 Python 垃圾回收自动释放，
必须显式 `release()`。
将 force 区间包在 `try/finally` 中，在运行时仍有效时释放；shutdown 只会对
仍记录为 active 的 force 发出警告并清空路径缓存，不会自动 release。
账本属于声明路径而不是单个 Python handle，SVX 不维护嵌套 force 栈，也不会
恢复更早的 force。多个调用者对同一路径操作时，需要自行协调。

**检查点：**
[层次信号访问示例](../examples/hierarchical_signal_access) 包含两态、四态、
read/write、force/release、订阅和启动期失败的完整路径。

经常读取但很少变化的控制/状态信号，可以显式订阅：

```python
with status.subscribe() as latest:
    initial = latest.read()
    svx.delay(10, "ns")
    observed = latest.read()
```

订阅时立即读取初值，之后原生值变化回调只复制数值，不执行 Python。
`latest.read()` 使用原有 SvTypes codec 解码缓存，不重新读取 HDL；四态值保留
X/Z，二态 codec 遇到 X/Z 仍报错。它表示“最近通知的值”，不是事件历史或
稳定采样点，同一调度区间内刚赋值时缓存可能仍旧；需要即时值时用
`status.read()`。单纯 `delay(0)` 不能保证 NBA 和下游逻辑均已稳定。
使用 `with` 或显式 `close()` 退订；关闭一个订阅不影响其他订阅。shutdown
也会移除剩余订阅，关闭或退出后读取会报错。垃圾回收不负责退订。
高频变化会产生回调和复制开销，不应据此将高速逐拍采样移到 Python。

## 11. 把每个新能力变成可维护的构建输入

不要把生成命令散落在终端历史中。给工程保留一个固定入口，依次完成声明发现、
桥接生成、必要的编译和运行。例子中的 `generate.py` 就承担这个职责。
完整的操作规则、变更矩阵、来源检查和恢复方法统一放在
[生成与增量构建指南](SVX_GENERATION_WORKFLOW.md)。

### 复用现有工程，而不是另配一套解析环境

保留工程原有 filelist、宏、include 路径及库搜索顺序，将这些输入交给 SVX。
参数形式与路径解释见[编译配置导入](SVX_BUILD_INPUTS.md)。
真实工程演示见 [UART 迁移教程](../examples/opentitan_uart/README.zh-CN.md)。
`-y` / `+libext` 按需选取库文件，不枚举目录下所有文件。

### 日常修改与只读验收分开

- 修改后：先刷新 manifest，再刷新桥接；桥接字节未变则不触发 SV 重编译。
- 验收已有产物：按同样顺序对两个命令运行 `--check`；第二步不能代替第一步。
- 改了原生库、SV 接口或数据契约：按变更矩阵重建受影响的部分。
- 改了 Python 行为：用新仿真进程加载，不把 shutdown 当作模块热重载。

不要为自动观测到的 Python 依赖再重复维护文件列表，也不要手改来源记录来
绕过过期检查。输出冲突时先判断所有权，不能通过清空生成目录掩盖问题。

### 项目验收清单

1. Python 和 SV 启动入口、构建输入与生成命令可从工程文件确定。
2. 正向场景通过，关键错误由负向场景确实触发。
3. Python-only 修改与需要重编译的修改分别验证。
4. 生成源码不承担用户逻辑；性能密集的逐样点工作保留在 SV。
5. 结果记录说明项目范围和已验证行为，不用版本号代替验证。

## 12. 按需查找完整示例

可选的[波形控制示例](../examples/waveform_control/README.zh-CN.md)演示
`svx.waveform`。它不替代层次信号读写：波形后端负责大量信号的变化记录，
Python 只控制录制区间、文件和 scope。接口默认禁用；先配置后端并编译可选
wrapper，再查询 `capabilities()`。`switch_file` 保留选择，`finish` 后的下一次
`begin` 重建选择；运行中 `add_scope` 不支持移除旧信号。

| 需求 | 示例 |
|---|---|
| 同一 DUT 的综合学习与维护路径 | [寄存器验证小项目](../examples/register_lab/README.zh-CN.md) |
| 从真实 UVM 环境逐步迁移、混合工作与验证故障 | [OpenTitan UART 迁移教程](../examples/opentitan_uart/README.zh-CN.md) |
| 最小初始化、加载、启动和延时 | [基础启动](../examples/milestone_1_basic) |
| fork/join、等待与停止 | [fork/join](../examples/milestone_1_fork) |
| Python 堆共享 | [共享状态](../examples/milestone_1_shared_state) |
| fatal traceback | [异常策略](../examples/milestone_1_error) |
| 原始 bytes/payload | [payload 通道](../examples/milestone_2_payload_channel) |
| SvTypes 类型化通道 | [类型化通道](../examples/milestone_2_typed_channel) |
| 已有 SV 验证环境 | [既有环境](../examples/milestone_5_existing_env) |
| CLI、生成和路径发现 | [CLI 工作流](../examples/milestone_6_cli_workflow) |
| SV 侧类型化辅助任务 | [类型化总线](../examples/milestone_7_sv_typed_helpers) |
| SV 基类由 Python 扩展 | [SV -> Python 继承](../examples/cross_language_inheritance) |
| Python 基类由 SV 扩展 | [Python -> SV 继承](../examples/python_owned_inheritance) |
| 外部 SV class handle 或 virtual interface | [外部 handle](../examples/foreign_handles) |
| 小规模层次信号访问 | [层次信号访问](../examples/hierarchical_signal_access) |

更完整的 API 形状请查阅 [API Reference](SVX_API_REFERENCE.md)，架构约束请查阅
[SVX 1.0 契约](SVX_1_0_REQUIRED_FEATURES.md)。本 Cookbook 的默认选择始终是：
让 SV 保持时间和硬件行为的所有权，让 Python 通过显式、SvTypes 化的边界表达
验证意图。
