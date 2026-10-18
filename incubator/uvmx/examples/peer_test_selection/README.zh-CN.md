# UVMX 对等用例启动

[English](README.md)

本示例通过同一个 UVM factory 和 `run_test()` 选择 Python 或原有 SV 用例。
用例定义、Python 状态和事务处理留在 Python；SV 只提供可复用 Test 接入、
phase 转发、驱动/监测基础设施及 objection 管理。
固定回调接入通过公开的 SVX CallbackAdapter 在运行时选择 Python 类，复用
SVX 现有对象工厂，在初始化前直接绑定用户 Test 实例；没有另设 UVMX 委托
对象，也没有另一套构造或分发机制。

```text
+UVM_TESTNAME=py_smoke_test
+UVM_TESTNAME=legacy_sv_test
```

## 首次构建

UVMX 位于 `incubator/uvmx`，不包含在 SVX 发布包中。Python 导入路径应包含
`incubator/uvmx/python` 和本示例目录；SV 包含路径应包含 `incubator/uvmx/sv`。
嵌入式 Python 还需能导入它的依赖包目录。

```sh
export PYTHONPATH="incubator/uvmx/python:incubator/uvmx/examples/peer_test_selection:python:../svtypes/python:."
mkdir -p generated
python -m svx svtypes-gen --module python_tests --package uvmx_types_pkg \
  --channel-helpers --out generated/uvmx_types.sv
python incubator/uvmx/tools/uvmx_gen.py --module python_tests \
  --sv-base-source incubator/uvmx/examples/peer_test_selection/base_test.sv \
  --sv-out generated/uvmx_generated.sv \
  --artifact-manifest generated/uvmx_artifact.json
```

按顺序编译 SvTypes/SVX 包、`incubator/uvmx/sv/uvmx_pkg.sv`、生成的数据包、
`base_test.sv`、生成的基类注册包和 `tb.sv`，构建并加载 SVX native 库。
Python 用例应输出 `UVMX Python run_phase complete`，SV monitor 应报告收到
类型化事务；SV 用例应报告 `legacy SV test selected`。两者均不得出现错误。

## 仅修改 Python 新增用例

首次构建后，在 `python_tests.py` 新增带 `@uvm_test` 的类，或在该模块导入
新文件中的用例。选择已编译的 `sv_base` 和唯一的 `factory_name`，随后使用
**同一个仿真可执行文件和 native 库**，通过新的 `+UVM_TESTNAME` 启动。
不要重新运行生成器或 SV 编译器。新增 Python 成员和受支持 phase 的重载也
不需要重新生成 SV。原有 SV 用例仍由同一 factory 正常启动。

生成器只为不同的自定义 SV 基类生成可复用注册，不生成逐用例 SV 类。
默认 `uvm_pkg::uvm_test` 桥接已内置。只有新增未编译的 SV 基类或改变 SV
可见契约时才需重新编译。启动时收发类型化注册元数据采用并行方式，用例
数量不受通道容量限制。与既有 SV 用例重名会明确失败，不会静默覆盖。

当前不是完整 UVM API：Python phase 只接收 `self`，构造不接收用户参数，
同步执行，function phase 和构造禁止延时。自定义 SV 基类仍须直接继承
`uvm_test`。详细支持范围及独立源码构建方式见英文说明。
