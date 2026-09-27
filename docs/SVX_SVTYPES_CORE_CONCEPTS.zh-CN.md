# SVX 与 SvTypes 核心概念、能力与机制讲解

> 面向第一次接触 SVX/SvTypes 的验证工程师。本文按照三张架构图的阅读顺序，将概念与示例串成一条完整路径：先定义数据，再启动跨语言运行时，随后使用 channel、信号服务和跨语言继承。

## 0. 三张图的阅读顺序

| 图 | 回答的问题 | 本文对应章节 |
| --- | --- | --- |
| [SVX 全景架构图](architecture/svx_architecture.excalidraw) | Python、`libsvx`、`svx_pkg` 和 SvTypes 如何组成整体？ | 1 至 6 |
| [Python 派生 SV 图](architecture/inheritance_python_extends_sv.excalidraw) | 如何让 Python 实现一个 SV 基类的派生类？ | 7 |
| [SV 派生 Python 图](architecture/inheritance_sv_extends_python.excalidraw) | 如何让 SV 实现一个 Python 基类的派生类？ | 8 |

这三张图不是三个彼此独立的功能：后两张图共享第一张图中的 runtime、对象表、Schema/codec、SvTypes 字段契约和调用栈保护。

## 1. 一句话模型

```text
SystemVerilog 管仿真时间、接口时序、driver、monitor、UVM/已有环境
Python 管测试意图、场景编排、事务构造、参考计算、检查策略
SvTypes 管跨语言传递的值、类型、编码与对象字段
SVX 管 Python <-> libsvx <-> SystemVerilog 之间的受控调用与传输
```

SVX 不是第二个仿真调度器，也不把 Python `async/await` 当作仿真并发模型。凡是会等待仿真时间、访问 simulator state 或调用 SVX primitive 的代码，都必须由 SVX 从一个活动的 SV 执行上下文启动。

## 2. 全景架构：四层各自负责什么

**配图：** [SVX 全景架构图](architecture/svx_architecture.excalidraw)。阅读本节时，沿图中 `Python -> native -> SystemVerilog -> SvTypes` 四个泳道向下看；本文的代码示例只使用泳道顶层的公开 API，不直接调用内部节点。

```text
Python: python/svx
  test/export, delay/fork/display, Channel, inheritance, Signal
                 | Python C extension
                 v
native: libsvx
  python_runtime, python_bindings, context, process, payload, sv_dpi, VPI
                 | DPI-C
                 v
SystemVerilog: svx_pkg
  svx_init/load/start/shutdown, timing, fork/process, channel, inheritance
                 |
                 v
SvTypes: 唯一值与对象契约
  Schema/codec, EncodingDescriptor, generated SV types, ExternalFieldStorage,
  RemoteRef
```

### 2.1 Python 层

Python 应放置测试、场景编排、配置数据、事务构造、参考模型和 scoreboarding policy。`@svx.test` 或 `@svx.export` 将零参数入口显式注册；普通 Python 函数本身不会自动成为 SV 可调用入口。

```python
# verification/tests/smoke.py
import svx

@svx.test
def smoke():
    svx.display("Python test is running in simulator context")
    svx.delay(10, "ns")
```

### 2.2 native 层：`libsvx`

`libsvx` 是 simulator-loadable C++ runtime。它嵌入/管理 Python、保存执行上下文、管理 payload 所有权，将 Python 调用映射到 SV DPI task/function，并在需要时调用 VPI 服务。

应用代码不应直接调用 `python_bindings`、`sv_dpi` 或 payload 原始接口。它们是支撑 `svx` Python API 与 `svx_pkg` SV API 的内部层。

### 2.3 SystemVerilog 层：`svx_pkg`

SV 侧负责在正确的仿真进程中启动 Python，并继续保留实际时间行为。

```systemverilog
`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  initial begin
    svx_init();
    svx_run_test("verification.tests.smoke", "smoke");
    svx_shutdown();
    $finish;
  end
endmodule
```

这里的执行路径是：

```text
SV initial -> svx_init -> libsvx 创建 Python runtime
           -> svx_run_test -> 导入 Python 模块、定位显式注册入口
           -> @svx.test 函数运行
           -> svx.delay -> SV task 等待仿真时间
           -> Python 函数返回 -> SV initial 继续
```

`svx.delay()` 并不让 Python 自己睡眠；它回到 simulator 进程等待，因此时钟、driver、monitor 与所有其他 SV 进程仍按 simulator 的规则运行。

### 2.4 SvTypes 层：唯一数据契约

SvTypes 不属于 SVX runtime。它定义数据的形状和二进制 codec，并生成与 Python 模型对应的 SV 类型和 packer。SVX 只传送经过 SvTypes 编码的显式值，不会在 crossing 时自动随机化或采样覆盖率。

一个 SvTypes 值的契约包括：

- Python 类型与字段结构；
- SV 对应声明；
- `unified_type_name`；
- 编码指纹与二进制格式版本；
- 必要时的对象引用或外部字段存储语义。

因此，双方即使都叫 `Packet`，只要 descriptor 不一致，也不能被当成同一种跨语言值。

## 3. 从数据模型开始：定义一次，生成两侧类型

下面是一个 APB 请求模型。它既是 Python 中的对象定义，也是 SV 生成物的来源。

```python
# verification/svtypes_models/apb_types.py
from svtypes import Bit, Int, SvObject, get_package, svobj

pkg = get_package("apb_types")

@svobj(registry=pkg)
class ApbReq(SvObject):
    id = Int()
    addr = Bit(32)
    data = Bit(32)
    write = Bit(1)

@svobj(registry=pkg)
class ApbRsp(SvObject):
    id = Int()
    error = Bit(1)
```

生成 SV 类型及 typed-channel helper：

```sh
python -m svx svtypes-gen \
  --module verification.svtypes_models.apb_types \
  --types ApbReq,ApbRsp \
  --channel-helpers \
  --out verification/sv/generated/apb_types_and_channels.sv
```

生成物应作为构建输入：要么提交到工程，要么在构建中确定性生成并用 `--check` 检查未过期。手写另一份结构相同的 SV class 会重新引入类型漂移风险。

## 4. 最常用协作机制：typed channel

channel 是高层事务跨语言流动的默认方式。它适合请求、响应、monitor observation 和比对结果；它不应取代每拍 pin 级数据路径。

### 4.1 Python 侧：构造事务并等待响应

```python
import svx
from verification.svtypes_models.apb_types import ApbReq, ApbRsp

@svx.test
def apb_smoke():
    bus = svx.reqrsp_channel("env.apb0", ApbReq, ApbRsp)

    req = ApbReq()
    req.id.value = 7
    req.addr.value = 0x1000
    req.data.value = 0x1234_5678
    req.write.value = 1

    rsp = bus.request(req)
    assert rsp.id.value == 7
    assert rsp.error.value == 0
```

`bus.request()` 不是 host-thread blocking queue；它通过 SVX 的受控等待机制把当前 Python/SV 执行上下文挂起，直到 SV driver 发布响应。

### 4.2 SV 侧：保留时序行为

```systemverilog
task automatic apb_driver();
  ApbReq req;
  ApbRsp rsp;

  forever begin
    svx_get_ApbReq("env.apb0.req", req);

    // 保留在 SV 的周期级操作：等待 ready、驱动 interface、处理 reset。
    drive_apb_transfer(req);

    rsp = new();
    rsp.id = req.id;
    rsp.error = 0;
    svx_put_ApbRsp("env.apb0.rsp", rsp);
  end
endtask
```

生成 helper 完成 SvTypes payload 的 kind、content type、类型 descriptor、编码和解码检查。应用代码不应自己拼 byte queue 或手动比较指纹。

### 4.3 monitor 与 checker

```python
from verification.svtypes_models.apb_types import ApbReq

@svx.test
def check_observation():
    mon = svx.mon_channel("env.apb0.mon", ApbReq)
    observed = mon.get()
    assert observed.addr.value == 0x1000
```

SV monitor 在它已有的 clocking block 或采样事件上取样，再以 `svx_put_ApbReq("env.apb0.mon", obs)` 发布。Python 收到的是事务，不是“某个 Python 收到回调时刻”的瞬时信号值。

## 5. Simulator-owned primitives 与 process 管理

**配图：** [SVX 全景架构图中的 `primitives`、`context`、`process`、`svx_timing` 与 `svx_process / fork`](architecture/svx_architecture.excalidraw)。它们共同解释为什么 Python 看似在“等待”或“并行”，实际仍是 simulator 在调度。

SVX primitive 用于让 Python 表达测试意图，同时不夺走 SV 对仿真调度的所有权。当前公开的 simulator-owned primitive 是 `display`、`delay`、`fork_join`、`fork_join_any` 与 `fork_join_none`，以及它们返回的 `ProcessGroup`。

### 5.1 `svx.display(message)`：受控的 simulator 日志点

```python
svx.display("configuration finished")
svx.display(f"received transaction {transaction_id}")
```

它将 `message` 转成字符串并交给当前 SVX 执行上下文输出。它适合 test/action 的关键状态、诊断和失败附近的上下文；大量逐样本打印仍应避免，否则会主导仿真时间和日志体积。

### 5.2 `svx.delay(value, unit)`：等待仿真时间，不是 host sleep

```python
svx.delay(5, "ns")
svx.delay(0.5, "ns")
svx.delay(1, "us")
```

支持的 unit 为 `s`、`ms`、`us`、`ns`、`ps`、`fs`。`value` 可以是非负有限 `int` 或 `float`；负数、无穷值、未知单位和超出 64 位 simulator tick 范围的值会在 Python 侧立即报错。

内部路径如下：

```text
Python svx.delay(5, "ns")
  -> libsvx 保存当前执行上下文和 process index
  -> exported DPI task delay_svx(5, ns)
  -> SV #5ns 等待，或等待 cancel event
  -> simulator 唤醒当前执行流
  -> Python 从 svx.delay() 返回
```

因此，`svx.delay()` 期间时钟、driver、monitor 和其他 SV process 正常推进。不要使用 `time.sleep()`、`asyncio.sleep()` 或 host-native timer 替代它们；那些操作不会推进仿真时间，还可能阻塞唯一的 Python 执行路径。

### 5.3 三种 fork 语义

```python
def short_check():
    svx.delay(1, "ns")

def long_check():
    svx.delay(3, "ns")

# 所有 child 完成后才返回。
all_done = svx.fork_join([short_check, long_check])
assert all_done.status().value == "finished"

# 首个 child 完成后返回；其余 child 仍由返回的 group 管理。
first_done = svx.fork_join_any([short_check, long_check])
first_done.kill()                 # 主动终止尚在运行的 child

# 创建后台 child 后立即返回；之后必须由测试显式等待或终止。
background = svx.fork_join_none([long_check])
background.await_()
```

语义与 SV 的 `fork ... join`、`join_any`、`join_none` 对应：

| API | 父 Python 调用何时返回 | 调用者对剩余 child 的责任 |
| --- | --- | --- |
| `fork_join([...])` | 全部 child 结束 | 无剩余 child |
| `fork_join_any([...])` | 任一 child 结束 | 对仍在运行者执行 `await_()` 或 `kill()` |
| `fork_join_none([...])` | child 已创建后立即返回 | 最终必须执行 `await_()` 或 `kill()` |

输入必须是非空的零参数 callable 列表/元组；空列表或非 callable 会立即报错。child 由 SV `fork` 与 `process` 监督，而不是通过 Python thread、`threading.Thread` 或 `asyncio.create_task` 创建。

### 5.4 `ProcessGroup`：观察、等待与取消

```python
group = svx.fork_join_none([long_check])

state = group.status()  # FINISHED / RUNNING / KILLED / UNKNOWN
if state.value == "running":
    group.kill()        # kill_running() 是同义别名

group.await_()          # 等待仍存在的 child；已被 kill 的 group 可安全收尾
```

`ProcessGroup` 使 parent 能把 child 的生命周期收束到当前测试范围。取消时，SVX 会向对应 SV process 发出取消请求；等待 `delay` 或 channel 的 child 被唤醒并终止，而不是遗留不可见的 host 线程。child 的异常也按 SVX 异常 policy 回报到 SV，而不是默默存在线程日志中。

### 5.5 primitive 的上下文边界

下列调用必须发生在 SVX 启动的活动执行上下文中：`delay`、channel 阻塞操作、inheritance callback、Signal 访问以及 fork child。它们适用于：

- `@svx.test` / `@svx.export` 入口及其同步调用链；
- SVX 生成的跨语言 task callback；
- `fork_join*` 创建的 child。

它们不适用于 import-time 顶层代码、普通 `pytest`、host thread、`async def`/awaitable callback 或未经 SVX 启动的 Python 脚本。纯数据建模、SvTypes randomize、参考算法等不访问 simulator 的工作可以脱离该上下文执行。

工程实践中，时钟、reset、driver、monitor 和 UVM phase 仍留在 SV；Python fork 更适合测试编排、等待多个 transaction 结果和有限期检查。

## 6. 小范围层次信号访问：Signal

Signal API 是对既有环境的窄接口，用于少量 setup 检查、诊断和 fault injection。它不是 driver/monitor 的替代品。

先集中声明全部路径：

```python
# verification/signal_declarations.py
import svx
from svtypes import Bit, Logic

status = svx.declare_signal("tb.dut.status", Bit(8))
fault_bus = svx.declare_signal("tb.dut.fault_bus", Logic(8))
```

SV 启动时一次性导入、解析并验证：

```systemverilog
initial begin
  svx_init_with_signal_declarations("verification.signal_declarations");
  svx_run_test("verification.tests.fault", "inject_fault");
  svx_shutdown();
end
```

Python 测试使用声明得到的 handle：

```python
import svx
from svtypes import LogicValue
from verification.signal_declarations import fault_bus, status

@svx.test
def inject_fault():
    assert status.read() == 0
    fault_bus.force(LogicValue.from_string("10xz01z0"))
    svx.delay(1, "ns")
    fault_bus.release()
```

其机制是 `Signal -> libsvx direct VPI service -> simulator hierarchy`。路径在启动后封存，不能按测试运行过程动态发现；`Bit` 读取到 X/Z 会失败，而 `Logic` 保留四态值。

## 7. 跨语言继承一：Python 派生 SV 类

**配图：** [Python 派生 SV 图](architecture/inheritance_python_extends_sv.excalidraw)。其中 `A -> AMirror -> B` 是本节的类层次；`object_id`、对象表、Schema/codec 和 `ExternalFieldStorage` 是两侧保持同一实例语义的支撑机制。

对应 `inheritance_python_extends_sv.excalidraw`。适用情况是：现有 SV 环境已经围绕一个 virtual 基类工作，希望将某个具体实现迁移到 Python，但仍让 SV 通过原有基类 handle 调用它。

### 7.1 用户看到的继承关系

```text
SV: A (真实基类)
      ^
      |  generated
SV: AMirror extends A  <---- object_id ---->  Python: AMirror
                                                ^
                                                |
                                      Python: B(AMirror)
```

SV 侧保留真实基类：

```systemverilog
package driver_pkg;
  virtual class BaseDriver;
    virtual task drive();
      $fatal(1, "BaseDriver.drive must be overridden");
    endtask
  endclass
endpackage
```

manifest 声明跨边界的真实事实：类 ID、语言归属、构造发起方、可调用 virtual 方法、task/function 属性和每个参数的 SvTypes binding。它是生成器和 runtime 的唯一 contract。

```json
{
  "canonical_id": "sv://driver_pkg/BaseDriver",
  "language": "sv",
  "symbol": "driver_pkg::BaseDriver",
  "constructor": {"initiator": "sv", "parameters": []},
  "methods": [{
    "canonical_id": "sv://driver_pkg/BaseDriver#drive",
    "name": "drive",
    "parameters": [],
    "return_type": "void",
    "timing": "task",
    "virtual": true
  }]
}
```

生成镜像：

```sh
python -m svx inheritance-gen \
  --manifest verification/inheritance.json \
  --python-out verification/generated/python \
  --sv-out verification/sv/generated/inheritance_mirrors.sv \
  --artifact-manifest verification/generated/svx-artifacts.json
```

Python 只继承生成的 mirror，并覆盖 manifest 中声明的方法：

```python
# verification/python_driver.py
import svx
from svx_mirrors.driver_pkg import BaseDriverMirror

class PythonDriver(BaseDriverMirror):
    def drive(self):
        svx.display("Python override")
        svx.delay(2, "ns")
```

SV 仍按原有基类使用它：

```systemverilog
BaseDriverMirror driver;

svx_init();
svx_load("verification.python_driver");
driver = new();             // 生成路径分配并绑定同一个 object_id
driver.drive();             // SV -> AMirror -> PythonDriver.drive()
svx_shutdown();
```

`drive` 是 task，因此 Python override 可以调用 `svx.delay`。若 manifest 将方法声明为 function，它必须是非阻塞的，不能消耗仿真时间。

### 7.2 运行时实际发生的事

```text
1. SV 构造 generated AMirror。
2. runtime 分配一个唯一 object_id，创建并绑定 Python B 实例。
3. SV 调用 handle.drive()。
4. AMirror 把“对象 ID + method ID + SvTypes request bytes”交给 libsvx。
5. libsvx 以活动 execution context 调用 Python override。
6. Python 返回 SvTypes response；SV 解码 copy-out/result 并继续执行。
```

SV 看到的是可赋值给 `BaseDriver` 的 SV 派生对象；Python 看到的是可调用基类声明方法的 Python 对象。两侧不是复制了两个独立业务对象，而是绑定到同一个跨语言对象身份。

## 8. 跨语言继承二：SV 派生 Python 类

**配图：** [SV 派生 Python 图](architecture/inheritance_sv_extends_python.excalidraw)。该图应与上一节对照阅读：构造发起方从 SV 变为 Python，SV factory 和 `BProxy` 因而成为入口，而 Schema/codec、对象表、字段契约和循环拒绝保持一致。

对应 `inheritance_sv_extends_python.excalidraw`。适用情况是：Python 拥有可复用抽象基类或策略类，而项目希望由 SV 提供一个具体实现，且 Python 应像使用普通子类一样构造和调用它。

### 8.1 用户看到的继承关系

```text
Python: B (SvObject / Python 基类)
           ^
           | generated Python mirror/proxy
SV: BProxy / AMirror
           ^
           |
SV: C extends BProxy
```

Python 声明基类。装饰器是 manifest 前端元数据；实际 runtime contract 仍是规范化后的 manifest。

```python
# verification/base_monitor.py
from svtypes import Int
from svx import Function, Task, inheritance_class, inheritance_method, inheritance_type

INT = inheritance_type(Int, sv="int", sv_packer="int_packer")

@inheritance_class(canonical_id="py://verification/BaseMonitor")
class BaseMonitor:
    def __init__(self, seed: int):
        self.seed = seed
        self.notified = False

    @inheritance_method
    def sample(self) -> Function[INT]:
        return 17

    @inheritance_method
    def notify(self) -> Task:
        self.notified = True
```

SV 实现具体派生类并继承生成的 proxy：

```systemverilog
class SvCounter extends BaseMonitorProxy;
  int calls;

  function new(longint unsigned object_id, int seed);
    super.new(object_id);
    calls = 0;
  endfunction

  virtual function int sample();
    calls++;
    return super.sample() + 25;
  endfunction

  virtual task notify();
    super.notify();
  endtask
endclass
```

Python 发起构造前，SV 注册 factory。factory 由 generated protocol 接收构造 request、用同一个 object ID 创建 `SvCounter`，并报告成功或错误。

```systemverilog
SvCounterFactory factory;

svx_init();
factory = new();
svx_inheritance_registry::register_factory(
  "py://verification/BaseMonitor", factory
);
svx_load("verification.python_test");
svx_start("verification.python_test.run");
svx_shutdown();
```

Python 使用生成的 Python proxy，调用形式保持自然：

```python
import svx
from svx_py.verification.base_monitor import BaseMonitor

@svx.test
def run():
    monitor = BaseMonitor(9)       # Python 发起，SV factory 创建 SvCounter
    assert monitor.sample() == 42  # Python -> SV override -> super() -> Python base
    monitor.notify()
    assert monitor.notified
```

### 8.2 为什么要有 factory 和 object table

SVX 不具备通用 SV object reflection，也无法观察任意手写 `new` 或可靠地追踪任意析构。因此跨语言对象必须由 generated construction path 创建：

```text
发起方 -> generated factory -> 分配 object_id -> 两侧对象创建 -> bind -> post-bind hook
```

如果任一步失败，runtime 回滚部分绑定。应用代码不手写 remote ID，也不直接操作 native 对象表。

## 9. 两种继承方向共同遵守的机制

### 9.1 manifest 限制调用面

不是任意方法名都可跨语言调用。只有 manifest 明确列出的 constructor、virtual method、参数方向、task/function 属性和 SvTypes 类型可被生成和分派。

这样做的直接收益是：生成物可审计、类型可校验、错误在生成/启动阶段暴露，而不是在某次任意字符串反射调用时才出现。

### 9.2 SvTypes 负责参数、返回值和字段

跨语言方法的每个 `input`、`output`、`inout` 和 result 都由 SvTypes 编码。`output`/`inout` 是响应中的 copy-out 值，不是两侧共享的 SV lvalue；因此 `ref` 与 `const ref` 被拒绝。

```text
SV task call
  -> SvTypes request bytes
  -> Python override
  -> SvTypes response bytes
  -> SV copy-out/result
```

字段也遵从这一规则。图中的 `SVXFieldStorage` 是 SvTypes `ExternalFieldStorage` 协议的一种实现：字段定义仍属于 SvTypes，而读写可在 object ID 与 manifest field ID 指向的外部实例上完成。它让投影字段保持声明的字段语义，不需要把每次修改都复制成两个独立状态。

### 9.3 `RemoteRef` 传递 handle，不传递所有权

若一个参数或返回值是另一跨语言对象的 handle，manifest 使用 `RemoteRef(target_type_name)`。它编码的是当前 registry 中的 opaque object ID；runtime 验证目标类型兼容性并取得对应代理。

```text
producer.make_child() -> RemoteRef(Child)
consumer.accept_child(ref) -> runtime 查 object_id 与类型 -> 调用目标
```

`RemoteRef` 不延长对象寿命。对象关闭或 `svx_shutdown()` 后，旧引用再次使用会得到 unknown/closed object 错误，而不是悄悄指向新对象。

### 9.4 `super()` 与循环拒绝

生成的 mirror/proxy 支持声明方法的跨语言 `super()`：例如 Python 调 SV 基类，或 SV override 回调 Python 基类。runtime 对当前调用帧维护对象 ID 与方法 ID 栈。

```text
合法：Python B.check -> super.check() -> SV A.check
拒绝：SV A.check -> Python B.check -> SV A.check -> ...
```

若活动帧重复，SVX 拒绝递归/阻塞循环并给出完整重复帧路径。设计方法时仍应避免“Python 配置 action 调 SV，而 SV 又同步回调同一个 Python action”的闭环。

### 9.5 生命周期

测试结束必须调用 `svx_shutdown()`。它清理 channel、继承对象表、投影字段绑定和其他 runtime 状态。需要提前确定性释放时，使用公开的 instance close API，而不是试图手工删除一侧对象。

## 10. 把能力组合为一个实际验证场景

下面以“Python 编排配置，SV 驱动与监测，Python 比对”为例串联能力。

```text
Python RxSchedule
  -> Python RxConfigAction extends generated SV RegAccessAction mirror
  -> SV register tasks
  -> SV driver / monitor
  -> typed observation channel
  -> Python reference model / checker
```

### 10.1 Python 配置 action 继承 SV 基类

```python
class RxConfigAction(RegAccessActionMirror):
    def configure_static_path(self):
        self.write_reg(0x100, 0x12)
        self.write_reg(0x104, 0x01)
        self.poll_reg(0x108, 0x1, 0x1)
```

`RegAccessActionMirror` 的 SV 基类仅保留真实寄存器访问 task；Python 拥有更高层的配置流程。该流程中的跨边界方法都必须在 manifest 中声明为 task，并使用 SvTypes 参数/返回值。

### 10.2 Python testcase 收集事务并比较

```python
@svx.test
def fixed_window_check():
    action = RxConfigAction()
    action.configure_static_path()
    svx.delay(100, "ns")       # 此处是该场景明确的稳定窗口前等待

    mon = svx.mon_channel("rx.output", Sample)
    expected = reference_model_for_fixed_profile()

    for index, expected_sample in enumerate(expected):
        actual = mon.get()
        assert actual.sequence_no.value == index
        assert actual.data == expected_sample
```

这里 channel 传输的是 monitor 已按 SV 接口时序采样的 `Sample`；Python 不直接高频轮询层次信号。若场景包含动态配置切换，必须先建立“配置何时在数据域生效”的单独契约，不能仅以寄存器写任务返回作为数字算法 golden 的切换点。

## 11. 选择正确机制

| 需求 | 首选机制 | 不应使用的替代品 |
| --- | --- | --- |
| Python 启动一个场景 | `@svx.test` + `svx_run_test` | 未注册模块函数的任意反射调用 |
| Python 等待仿真时间 | `svx.delay` | `time.sleep`、`asyncio` |
| 请求/响应或监测事务 | SvTypes typed channel | 手写 byte payload、频繁 signal polling |
| 小范围调试、setup、force/release | predeclared Signal API | 大规模 driver/monitor 数据通路 |
| Python 替换 SV virtual 类实现 | SV-owned manifest + generated AMirror | 手写双对象同步或 raw object ID |
| SV 实现 Python 抽象基类 | Python-owned manifest + generated proxy + SV factory | Python 把普通 SV handle 强行包装成镜像 |
| 传递跨语言对象 handle | manifest `RemoteRef` | 把 simulator handle 当整数/字符串传递 |

## 12. 最终记忆点

1. **SVX 决定跨语言行为如何发生；SvTypes 决定跨语言数据是什么。**
2. **SV 保留时间和接口语义；Python 获得测试意图和检查策略。**
3. **channel 是事务边界，Signal 是窄而显式的诊断边界。**
4. **跨语言继承靠 manifest 生成 mirror/proxy，不靠运行时任意反射。**
5. **一个跨语言对象只有一个由 runtime 管理的 object ID；`RemoteRef` 只借用它。**
6. **task 可以等待仿真时间，function 不可以；`ref` 不跨语言传递。**
7. **应用代码使用公开 Python/SV API；不要直接操作 generated dispatcher、payload 或 native registry。**
