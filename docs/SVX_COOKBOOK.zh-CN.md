# SVX Cookbook：从运行时基础到跨语言验证

本 Cookbook 是一条可顺序执行的 SVX 上手路径。它不要求重构已有
SystemVerilog 验证环境：先建立一个由仿真器调度的 Python 入口，再逐步
加入 SvTypes 数据、通道、继承和层次信号访问。

每一步都说明三件事：应放在 SystemVerilog 还是 Python、为何如此，以及
如何在本仓库的完整示例中验证。除非一节明确说明，否则继续使用上一节建立
的环境。

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

SVX 开发时使用相邻的 SvTypes 源码。以下命令在 SVX 仓库根目录执行：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pytest
PYTHONPATH=../svtypes/python python -m pip install -e .
```

构建供仿真进程加载的原生库。层次信号访问需要直接 VPI 服务，因此发布或要
使用信号访问时应显式要求对应头文件：

```sh
cmake -S . -B build \
  -DSVX_SIMULATOR_INCLUDE_DIR=/path/to/simulator/include \
  -DSVX_REQUIRE_DIRECT_VPI=ON
cmake --build build -j2
```

没有 VPI 头文件的普通 CMake 构建仍可用于 Python 和核心运行库开发，但其信号
服务是不可用的 stub，不能运行第 10 步。

让项目构建脚本从 SVX 查询输入，而不是写死本机路径：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx sv-files
PYTHONPATH=python:../svtypes/python:. python -m svx compile-flags
SVX_LIB_DIR="$PWD/build" PYTHONPATH=python:../svtypes/python:. python -m svx libs
```

将 `svx sv-files` 输出的 SvTypes SV 运行时文件与 `svx_pkg.sv`、项目的 `tb.sv`
及生成文件一起编译，并按目标工具的正常 DPI 方式加载 `svx libs` 输出的库。
确保仿真进程的 `PYTHONPATH` 同时包含项目根、`python` 和 `../svtypes/python`。

各示例共用的环境、生成、编译输入、library 加载与结果判定步骤见
[示例运行指南](../examples/RUNNING_EXAMPLES.zh-CN.md)；后续各节只补充该能力
特有的输入和检查点。

**检查点：**

```sh
PYTHONPATH=python:../svtypes/python:. .venv/bin/python -m pytest -q
```

应通过纯 Python 契约测试。完整的最小工程在
[基础启动示例](../examples/milestone_1_basic)。

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

SVX 的推荐首个落点不是重写 testbench，而是在既有 driver 和 monitor 的事务
边界接通类型化通道：

1. 在已有 SV 初始化路径调用 `svx_init()`。
2. 与现有 driver/monitor 并发启动一个 `svx_run_test()` 或 `svx_start()`。
3. driver 从 `<env>.<agent>.req` 取得 SvTypes item，按原来的时钟和协议驱动。
4. monitor 仍在 SV 时钟边沿采样，并向 `<env>.<agent>.mon` 发布 observation。
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

`REPORT` 不会制造默认返回值；调用边界仍会看到失败状态。错误策略、原语参数和
payload metadata 错误均有专用 `SVXError` 子类。

每次仿真收尾都遵守以下顺序：让已知 SVX 工作完成或显式 `kill()`，调用
`svx_shutdown()`，然后 `$finish`。关闭后保留的 channel、signal 或跨语言对象
引用是 stale，不能在下一次会话复用。

**检查点：** [异常示例](../examples/milestone_1_error) 展示 fatal traceback；
关闭和失效规则可结合第 3 步进程组示例观察。

## 9. 需要面向对象扩展时，使用声明式跨语言继承

仅当扩展点本来就是一个稳定的类接口时使用跨语言继承。它不是任意对象反射：
方法、虚分派、参数、返回值、字段和继承链都需要出现在 manifest 中。

### 9.1 SV 基类由 Python 派生

适用情形：SV 已有 `virtual class BaseDriver`，希望 Python 编写某个 virtual
override，且 SV 仍拥有对象构造和使用位置。

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
5. SV 通过生成构造路径创建对象并调用其虚方法。

若通过 Python declaration front end 编写 manifest，推荐直接从 Python 原型生成：

```python
@svx.inheritance_method
def calculate(
    self,
    source: INT,
    changed: svx.Inout[INT],
    observed: svx.Output[INT] = None,
) -> svx.Function[INT]:
    return source + changed
```

未包裹的 `INT` 与 `svx.Input[INT]` 都表示 `input`；`Inout`、`Output` 和
`Function[INT]` 分别表达其方向、返回值和 function transport。每个参数独立标记，
一个方向标记不会影响后续参数。`-> svx.Task` 表达可消耗仿真时间的 task。
`Output` 不会作为 Python 调用参数，故必须位于末尾并带默认值，结果通过 response
返回。未使用原型标注的既有代码仍可使用 `parameters=`、`return_type=` 和 `timing=`。

完整操作见 [SV 基类 -> Python 派生示例](../examples/cross_language_inheritance)。

### 9.2 Python 基类由 SV 派生

适用情形：Python 拥有 base 的构造和场景逻辑，SV 提供具体、与硬件紧密相关的
派生实现。

1. 在 manifest 中声明**Python base**、`constructor.initiator: "python"` 和全部
   crossing 方法。此方向的 manifest canonical class ID 是该 Python base，而不是
   应用 SV 派生类的名字。
2. 用同一 `inheritance-gen` 命令生成 `svx_proxy_<python_module>::BaseMonitor` 和 Python/SV adapter。
3. 用户在 SV 中定义具体派生类，让它继承生成的 Proxy，并把生成 Proxy 的
   constructor request 解码后传给自己的 `new`：

   ```systemverilog
   class SvCounter extends svx_proxy_base_monitor::BaseMonitor;
     function new(longint unsigned object_id, int seed);
       super.new(object_id);
       // 保存应用自己的构造状态。
     endfunction
   endclass
   ```

4. 用户实现 `svx_pkg::svx_factory`：用 `svx_proxy_base_monitor::BaseMonitor` 的生成 decoder 解码
   constructor request，创建 `SvCounter(object_id, seed)`，并在 `svx_init()` 后、
   Python 创建 base 前，以 **Python base 的 manifest ID** 调用
   `svx_inheritance_registry::register_factory(...)` 注册该 factory。
5. Python 创建生成的 Python base view；SVX 分配唯一 object ID，调用已注册的
   factory 创建并绑定 SV companion。随后 Python 调用会分派至 SV override，SV
   可以用 `super()` 回到 Python base。

完整操作见 [Python 基类 -> SV 派生示例](../examples/python_owned_inheritance)。

### 9.3 必须遵守的边界

- 只支持单继承、线性 lineage；多继承、mixin、字段遮蔽、未声明成员和方法重载
  会在生成期拒绝。
- `virtual` 方法用于跨边界动态分派。非 virtual 和静态方法仍可按 manifest
  包装调用，但不会改变 SV 的正常静态分派。
- `input`、`output`、`inout` 和返回值使用 SvTypes response；`ref` 与
  `const ref` 跨继承边界不支持。
- 不支持把任意已经存在的 SV handle 接管为镜像。每个跨语言对象都必须由生成的
  构造器或 factory 创建，才能保证 object ID、生命周期和字段驻留一致。
- 若把 Python 声明的 SvTypes 字段投影给后续 SV 派生类，需要
  `svtypes.external-field-storage.v1`；只有最终投影目标中的字段驻留在 SV。
- 同一 receiver/method 的同步回调循环会被检测并拒绝，避免两个语言互相等待。

生成后将 `SVX_ARTIFACT_MANIFEST` 指向 artifact manifest；在 build gate 中运行
同一命令加 `--check`，拒绝过期生成物。

### 9.1 传递外部 class handle 与 virtual interface

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
data.release()
status.write(LogicValue.from_string("10xz01z0"))
```

初始化会一次性解析并验证所有路径的 VPI 对象类别、宽度和 signedness。`Bit` 等
两态 codec 读取到 `X/Z` 时会失败，绝不偷偷压缩为 0/1；`Logic` 使用
`LogicValue` 保存 value、X、Z 三个平面。force 不依赖 Python 垃圾回收自动释放，
必须显式 `release()`。

**检查点：**
[层次信号访问示例](../examples/hierarchical_signal_access) 包含两态、四态、
read/write、force/release 和启动期失败的完整路径。

## 11. 把每个新能力变成可维护的构建输入

将以下项目纳入项目构建或 CI：

1. 使用 `svx svtypes-gen` 生成 SvTypes SV 类型及通道辅助任务。
2. 使用 `svx inheritance-gen --check` 检查跨语言生成物没有过期。
3. 通过 `svx compile-flags` 和 `svx libs` 获取 SVX 输入，而不是硬编码安装路径。
4. 运行 Python 测试，验证模型、manifest、生成器和不依赖仿真器的 API。
5. 在目标仿真配置中运行对应的 SV/Python integration source。
6. 对启用层次信号访问的 build 使用直接 VPI 原生库配置。

推荐的采用顺序是：第 2 步最小入口 -> 第 4、5 步类型化通道 -> 第 7 步接入现有
环境 -> 按需选择第 9 步继承或第 10 步信号访问。这样每次只增加一个边界，也最容易
定位契约、调度或编码问题。

## 12. 按需查找完整示例

| 需求 | 示例 |
|---|---|
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
