# 准备和使用 UVMX

[English](UVMX_GETTING_STARTED.md)

本指南假设现有工程已经能运行 UVM，并且 SVX 的 Python 包、SvTypes、SV 包和
native 运行库都已准备好。目标是接入一个 Python Test，同时继续通过原生
`run_test()` 和 `+UVM_TESTNAME` 选择 Python 或原有 SV 用例。

先使用默认 `uvm_test` 路径：**不需要生成逐用例 SV 类，也不需要运行 UVMX
基类注册生成器**。只有选用尚未编译的自定义 SV 基类或引入新的 SV 可见数据
契约时，才增加对应的生成和编译步骤。

## 1. 获取源码并设置 Python 路径

UVMX 暂时位于 SVX 源码仓库的 `incubator/uvmx`，不包含在 SVX 发布包中。
即使已经安装 SVX，也仍需取得这份 UVMX 源码；目前不使用 `pip install uvmx`。

以下命令从用户工程根目录执行，替换第一行的路径：

```sh
export UVMX_ROOT="/path/to/svx/incubator/uvmx"
export PROJECT_ROOT="$PWD"
export PYTHONPATH="$UVMX_ROOT/python:$PROJECT_ROOT:${PYTHONPATH:-}"
python -c 'import svx, svtypes, uvmx; print("UVMX_IMPORT_OK")'
```

保留已有 SVX/SvTypes 路径，不要覆盖原来的配置。仿真器内嵌 Python 也必须使用
这套导入路径；只在另一个终端能导入，不代表仿真进程一定能导入。
`UVMX_IMPORT_OK` 只证明导入准备完成，还没有运行仿真。

## 2. 编写默认基类的 Python 用例

在工程根目录创建 `my_tests.py`：

```python
"""Default-base UVMX startup without generated test or base registrations."""

import svx
from uvmx import Test, uvm_test


@uvm_test(
    canonical_id="py://verification/SmokeTest",
    factory_name="python_smoke",
)
class SmokeTest(Test):
    def run_phase(self):
        svx.display("UVMX_MINIMAL_START")
        svx.delay(2, "ns")
        svx.display("UVMX_MINIMAL_PASS")
```

这里不写 `sv_base`，因此使用已经内置的 `uvm_pkg::uvm_test`。Python 方法同步
执行；不要使用 `async/await`。此最小用例没有新事务声明，不需要 `svtypes-gen`。
它只验证用例启动和时序接通，不会自动创建或映射已有验证环境。

## 3. 接入原生 UVM 入口

新建最小 `tb.sv`，或将已有顶层中的唯一一处启动代码改为同样的顺序：

```systemverilog
module tb;
  timeunit 1ns;
  timeprecision 1ps;

  initial begin
    uvmx_pkg::uvmx_init("my_tests");
    uvm_pkg::run_test();
  end
endmodule
```

初始化会导入入口模块及其导入模块中的所有 `@uvm_test` 声明，全部注册到原有
UVM factory 后才返回。不要并行运行注册和 `run_test()`，也不要保留第二处
`run_test()`。用户不需要再单独调用 `svx_init()` 或启动某个 Python 用例入口。

UVMX 不改变 `finish_on_completion`。原生 UVM 默认会结束仿真，不能依赖
`run_test()` 之后的代码完成清理。若工程自行设置为返回模式，可在返回后调用
现有 `svx_shutdown()` 再退出；它是 task，不能从 `final` 调用。

## 4. 首次加入固定 SV 支持包

复用原工程的 UVM 配置、SVX native 库加载方式和既有 SvTypes/SVX 编译输入，
只增加 UVMX 固定包及新的顶层入口：

| 编译顺序 | 输入 | 操作 |
|---|---|---|
| 1 | 原工程的 UVM 配置或 UVM package | 保留既有方式，不重复编译隐式加载的包 |
| 2 | SvTypes、SVX package | 复用已准备好的输入，可用 `svx sv-files` 查询 |
| 3 | `$UVMX_ROOT/sv/uvmx_pkg.sv` | 加入编译清单 |
| 4 | 原有环境、SV Test 及用户 `tb.sv` | 保留原有用例，替换唯一启动入口 |

增加 SV include 路径 `$UVMX_ROOT/sv`，同时保留原有 UVM macros、SVX 和 SvTypes
include 路径。`uvmx_pkg.sv` 已包含注册记录、回调、factory 和初始化实现，
不要将它包含的各个 `.sv` 文件再次单独编译。继续加载原先已可用的 SVX native
库，无需因为新增此默认基类用例而重新构建该库。

最小路径没有自定义 SV 基类注册包，也没有用户事务生成包，**不运行
`uvmx_gen.py`，不需要额外的 `uvmx_generated_pkg` import**。
完整最小源文件位于 `incubator/uvmx/examples/minimal_test`。

## 5. 运行和后续新增用例

启动编译好的仿真程序，追加：

```text
+UVM_TESTNAME=python_smoke
```

应看到 `UVMX_MINIMAL_START` 和 `UVMX_MINIMAL_PASS`，用例同步等待 2 ns，且没有
UVM/SVX 错误。选择原有 SV 用例时使用它原来的 `+UVM_TESTNAME` 名称。

该最小源文件已于 2026-10-30 完成仿真验证：只编译固定包与顶层，未调用生成器，
复用已有 native 库，2 ns 正常结束，UVM warning/error/fatal 均为 0。

后续可在 `my_tests.py` 定义多个用例，也可让它只做聚合导入，例如：

```python
from verification.smoke import SmokeTest
from verification.reset import ResetTest
```

被导入的类需要各自使用 `@uvm_test` 和唯一的 `factory_name`。未导入的文件不会
自动被扫描。只新增或修改 Python 用例、状态、算法和受支持 phase，继续使用
已编译基类及已有数据契约时，不再运行生成器或编译器；重启同一个仿真程序，
通过新的 `+UVM_TESTNAME` 选择即可。这不是仿真运行中的热加载。

## 6. 可选的自定义 SV 基类和事务

若需要沿用已有 SV Test 基类来建立环境，在 Python 声明中显式选择：

```python
@uvm_test(
    canonical_id="py://verification/SmokeTest",
    factory_name="python_smoke",
    sv_base="env_pkg::EnvBaseTest",
)
class SmokeTest(Test):
    def run_phase(self):
        ...
```

当前自定义基类须直接继承 `uvm_test`。首次使用这个基类时，执行：

```sh
python "$UVMX_ROOT/tools/uvmx_gen.py" \
  --module my_tests \
  --sv-base-source verification/env_base_test.sv \
  --sv-out generated/uvmx_bases.sv \
  --artifact-manifest generated/uvmx_artifacts.json
```

在固定 UVMX 包之后、顶层之前编译 `env_pkg` 和生成的 `uvmx_bases.sv`，并在
顶层导入生成的 `uvmx_generated_pkg`。生成器只注册不同的 SV 基类，不为每个
Python 用例生成类。后续新增用例复用这个基类时，不需要再次生成或编译。
选用 SV 基类不会自动把它的成员暴露给 Python；实际事务服务仍通过显式 SVX
类映射或 SvTypes 通道接入。

| 情况 | 是否增加生成步骤 |
|---|---|
| 默认 `uvm_test`，无新增 SV 可见事务 | 不需要 |
| 新 Python 用例复用已有基类和数据契约 | 不需要 |
| 使用尚未编译的自定义 SV Test 基类 | 运行 `uvmx_gen.py`，编译新增基类注册 |
| 增加或改变 SV 侧消费的 SvTypes 事务 | 按原 SVX 工作流生成数据/通道代码并编译 |

进一步学习可使用源码中的 `incubator/uvmx/examples/peer_test_selection` 和
`incubator/uvmx/examples/register_lab`；前者的自定义基类和 typed transaction
生成步骤属于该示例，不是默认 UVMX 启动路径的必选步骤。
