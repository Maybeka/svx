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
python -m pip install -e ../svtypes
python -m pip install -e '.[dev,manifest]'
```

SVX 要求 SvTypes `>=1.4.2,<2.0.0`，包含公共 `SvObject.codec_template()`、
外部字段快照及随机化发布等修复；`1.4.1` 不足以满足这些契约。开发时使用
上述相邻源码依赖。SVX 启动会在创建 codec session 前检查必需接口，不会仅凭版本号
或格式 capability 判断兼容。发布依赖范围见
[发布契约](RELEASE_1.0.0.md#compatibility)。

构建供仿真进程加载的原生库。层次信号访问需要直接 VPI 服务，因此发布或要
使用信号访问时应显式要求对应头文件：

```sh
cmake -S . -B build \
  -DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')" \
  -DSVX_SIMULATOR_INCLUDE_DIR=/path/to/simulator/include \
  -DSVX_REQUIRE_DIRECT_VPI=ON
cmake --build build -j2
```

安装、原生库构建与仿真中嵌入的 Python 必须使用一致的解释器。切换解释器时，
使用新的构建目录，避免 CMake 缓存保留旧 ABI。仅构建成功不证明仿真加载成功；
原生库还需要仿真器提供 DPI 符号，不能以普通 Python 进程导入代替仿真验证。

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
限定静态调用。另一个构造缺口是多段
继承中的参数计算：内部阶段式路径会检查 Python `super().__init__(...)`
的参数是否与已完成的 SV 基类构造一致，不能把 Python 初始化体新计算的
参数送回已经执行完的基类构造。这不意味着设计禁止 `super(seed + 1)`；
自然构造顺序和独立祖先参数路由仍需完整实现。下面的单一 factory 示例
不能作为这些路径已经可用的证明。

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
  完整 Python-root 交替链仍受前述生成流程缺口影响。
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
read/write、force/release 和启动期失败的完整路径。

## 11. 把每个新能力变成可维护的构建输入

重复生成不会改写内容相同的产物或更新时间戳。生成器在写入前验证契约、
metadata、目标路径和已有文件的归属；不会覆盖普通用户 JSON 作为 artifact
manifest。已知的路径冲突或契约失败不会更新已有产物，也不会删除旧生成模块。
文件替换是逐文件原子的，不是整组事务；若写入期间发生 I/O 中断，重新生成并
执行 `--check` 后再构建。仅修改 Python 方法体不要求重编译未变的 SV 桥接，
但已追踪源码的来源和 artifact 记录需要刷新，并重新启动仿真加载新代码。

日常编辑方法体时，即使没有 `--python-source`，自动发现来源和生成导入记录
也会检测已追踪源码的变化。使用原参数按顺序重新执行发现和生成，两步成功后
可继续运行；只读验收使用下文的两道 `--check` 门禁，不是每次刷新都重复执行。
未变的 manifest 契约和桥接文件保持原时间戳，不需要因此重编译。
未追踪输入的修改无需刷新这些记录，但检查也不认证这些输入。
新仿真进程中的 `svx_load` 首次导入读取当前 Python 源码（包括该次导入的源码
依赖），不因同一秒内的等长编辑而使用旧字节码。已导入模块仍被缓存，不支持
在同一仿真进程中热重载。
把发现和生成命令及其参数固定在项目构建脚本中，生成与检查
复用同一组参数，不要每次手工输入两套命令。当前 CLI 不会自动恢复发现命令
或推断完整源码依赖，因此构建脚本仍需维护这些输入。

若需要显式源码审计，可在 `inheritance-gen` 中重复传入
`--python-source FILE`，记录项目选定的 Python 声明、实现或 codec 工厂文件
摘要；记录过程不会执行这些文件，也不会自动追踪它们的导入依赖。这些文件
受输出覆盖和旧产物清理保护。选择此审计后，即使只改方法体，`--check` 也会
报告输入记录过期，需要重新执行生成命令刷新 artifact 清单。内容未变的桥接
源码及时间戳保持不变，不需要因此重编译 SV。声明变更仍需先重新发现 manifest，
不能用刷新摘要代替契约更新。
过期诊断会列出变更、新增、移除的输入文件和变化的解析配置。若生成的桥接
文件及其他 artifact 元数据都一致，仅 Python 输入记录变化，提示会明确区分
这种情况。它不证明未跟踪的构建输入仍有效；SV 原始源码变化时，即使 adapter
没变，也要重新编译受影响的 SV 源码。
生成器会在 manifest 实例化前记录所选输入指纹，并在返回检查结果或写入生成
文件前再次核验。检测到输入途中变化或消失时，本次命令拒绝写入；等输入稳定
后重试。artifact 使用最初记录的指纹，不会悄悄采用生成途中的新版本摘要。
这不是源码锁或文件系统快照，也不会回滚用户 codec 工厂自己的副作用。
生成过程中新加载的普通 codec 工厂模块及其源码依赖，也会直接读取当前源码，
并在返回检查结果或写入产物前核验。途中变更或消失会拒绝本次命令；这些已
读取的源码不能被输出或旧产物清理覆盖，即使带有旧生成文件标记。这项本次
命令保护同时将实际编译的普通用户源码摘要加入 artifact 的自动导入记录；
它不刷新缓存模块或替代自定义加载器。
前一步 `inheritance-manifest` 同样核验显式 SV 声明文件、所选 SV 源码依赖和
有源文件的 Python 入口模块；发现途中变化或删除时保留原 manifest 并要求重试。
发现时也可重复传入 `--python-source FILE`，保护额外声明或 codec 辅助文件；
该选项本身不导入文件，缺失文件会在入口导入前失败，输出也不能覆盖这些输入。
发现记录会持久保存显式输入及实际编译的普通用户源码，后续
`inheritance-gen` 会消费并核验这些来源，无需再次逐个列出已记录的发现依赖。
仅为未被观察到的额外构建输入使用显式文件列表；文件摘要不证明缓存或自定义
执行代码的完整来源。
发现阶段仍会导入 Python 模块，不能回滚导入副作用。入口导入过程中实际加载的
普通源码依赖，以及声明解析或 codec 工厂例化时才导入的普通源码，会自动纳入
本次稳定性检查与覆盖保护，不必逐个显式列出。
编辑 Python 声明后应在新命令进程中重新发现；此检查不会自动刷新长驻 Python
调用者已经缓存的模块。
新导入的普通文件系统入口、其父包及源码路径被 `--python-source` 显式列出的
辅助模块，以及发现和 codec 例化过程中继续导入的普通源码依赖，会直接编译当前
源码，不信任仅按时间戳和长度判断的旧 `.pyc`。保护在入口定位前启用，也覆盖
父包初始化提前导入入口的情况，且持续到 manifest 序列化完成。已缓存模块、
本次发现命令之外的导入和自定义加载器仍遵循 Python 原有导入行为。
加载器记录实际编译的源码字节，并在输出前核验；即使入口在父包导入期间、
正式入口指纹记录前自编辑，也会拒绝输出。被读取的父包、入口、显式辅助文件
和上述传递源码依赖受覆盖保护；这不回滚导入副作用，也不代表完整依赖快照。
发现命令自动生成与 manifest 配套的 `<manifest-name>.svx-discovery.json`，
记录契约摘要、解析选项及实际读取的普通用户源码；生成阶段在解析类之前
核验它们。只在发现阶段读取的普通依赖不再要求重复列给生成命令。
必须保留配套文件，缺失或过期不会退回手写 manifest 模式。
发现命令先准备两份变化文件，再发布；发布异常且恢复成功时，原有文件及其
时间戳、权限保持不变，新发布的文件撤回。解决错误后重试发现命令即可。
若恢复也失败，错误会列出保留的原文件备份：保留备份，核对并恢复配套文件，
不要通过删除整个产物目录绕过问题。这不是断电安全事务，也没有多个写入者
之间的锁；同一配套文件只使用一个写入进程。发布期间读取方可能看到不完整
记录，此时必须拒绝。该恢复机制不覆盖全部桥接产物。
生成阶段实际编译的普通用户源码依赖则自动记录为 artifact 的
`generation_inputs.python_imports`：即使
桥接文本不变，源码改动也会使 `--check` 报旧；重新生成只刷新变化的记录，
不改未变桥接的时间戳。进程内重复调用保留已审计的缓存导入；其源码改变时
拒绝用旧模块认证新源码，要求使用新命令进程。自定义加载器和加载器作用域外
的导入不由这项机制追踪，不能视作完整依赖快照。
Python 标准库、SVX/SvTypes 及源码解析器的实现模块不列入自动用户依赖，避免是否预加载工具链影响
产物新鲜度；本次实际读取的源码仍受稳定性与覆盖保护，显式 `--python-source`
也不受这一排除规则影响。检查会用当前框架重新生成桥接；用户依赖记录不是
框架安装版本的锁文件。
标准库排除同时核对解释器的实际目录与标准模块名；不会按名字排除同名用户
模块，也不会笼统排除第三方安装包。显式列入的标准库文件仍接受摘要核验和
覆盖保护。
包含 SV 源码的发现记录还会重放有序源文件、include 搜索顺序、宏和编译单元
模式，比较实际选中的依赖身份。新增更高优先级同名头文件，即使内容相同，
也要求重新发现，而不是继续认证旧选择。此类检查需要 `manifest` 安装 extra，
生成命令不重复 `--sv-source` 也一样；旧记录缺少选择清单时重新发现即可。
交互式刷新使用原发现、生成命令（不带 `--check`）依次更新，只有两步都成功才
继续编译或运行。写入命令本身已有来源和产物所有权核验，无需紧接着再重复
两次只读检查。未变桥接保持时间戳，可继续复用相应编译产物；命令失败时不能
因为旧产物还存在就继续运行。
对于由源码声明发现的 manifest，验证现有产物的只读构建、CI 或发布门禁必须按顺序执行 `inheritance-manifest --check` 和
`inheritance-gen --check`，且使用各自生成时相同的输入/解析选项，具体命令见
[迭代开发](SVX_USER_MANUAL.md#21-iterative-development)。发现检查失败先更新
声明/metadata并重新发现，再生成桥接。方法体变更也需刷新来源记录，但
未变 manifest 与桥接不重写、不改时间戳。发现通过且仅已审计 Python 输入摘要
变化时，刷新生成记录即可，不必重编译未变桥接。只对旧 manifest 刷新摘要再
检查 artifact，手写/legacy 无来源引用时可能掩盖尚未发现的方法原型变化，
不能作为完整构建门禁。已缓存入口需要当前有效的发现证据，否则使用新命令
进程；自定义加载器和未经审计的缓存依赖仍不是完整发现图。
新审计声明源码执行普通导入时，还会核验缓存辅助模块：没有当前有效的旧发现
证据，则在写产物前拒绝，包括 `from`、相对导入和 `importlib.import_module()`。
文件未改也不能证明缓存定义来自这些字节；应使用新命令进程，不是补上
`--python-source`。有有效旧证据的缓存可复用，不重写未变产物。已有对象引用、
自定义加载器，以及源码执行边界之外的材料化导入仍未形成完整来源保证。
发现记录还保存普通文件模块名与实际源码路径；消费阶段在解析类之前，按
当前文件系统搜索路径核验选择，不执行包初始化，也不信任缓存模块路径。
新增更高优先级同名模块会拒绝旧记录；旧 Python 入口记录缺少选择清单时，
重新发现即可。检查必须使用当前应用的导入路径。自定义加载器、运行时修改
包搜索路径仍未被认证。参与这些模块解析的 namespace 祖先及有序目录也会
记录：新增包初始化文件，或者增加、重排目录，即使子模块路径不变也会拒绝
旧证据；旧 namespace 记录不完整时重新发现。继续保留两阶段顺序检查。
手写 manifest 没有发现命令；此时需显式更新其中的边界契约，再检查生成物，
不能期待 artifact 检查自动识别源码原型变化。

`--check` 也检查 Python 和分阶段 SV 的生成文件清单，缺失或陈旧清单不能通过。
这些隐藏 inventory 文件属于生成构建输入，不应手工编辑或省略。重新生成能
恢复当前清单。清单路径必须是规范的相对路径；绝对路径、含 `..` 的路径、
重复文件身份，以及作为待清理旧文件的符号链接会在写入前被拒绝，避免误删
本轮输出。不要通过直接删除清单来绕过诊断，应保留有效 metadata 以恢复归属。
上一份 artifact manifest 也可恢复历史归属：只有其中记录、
位于当前输出根目录、生成标记和 SHA-256 均匹配的旧产物才会被删除。修改过
的旧文件会在写入前报错；目录外、未记录的文件及本轮另作输出的路径不会删除。
若历史 inventory 与 artifact manifest 都丢失，不能凭当前声明推断旧文件归属，
因此应将这些 metadata 一并保留，而不是自动清空输出目录。

将以下项目纳入项目构建或 CI：

1. 使用 `svx svtypes-gen` 生成 SvTypes SV 类型及通道辅助任务。
2. 对源码发现的 manifest，先用原发现命令加 `--check` 检查声明，再执行
   `svx inheritance-gen --check`；手写 manifest 先显式更新契约再检查生成物。
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
