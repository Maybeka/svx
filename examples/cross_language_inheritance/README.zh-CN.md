# 跨语言继承

[English](README.md)

当已有 SystemVerilog virtual base class 需要获得 Python 实现，同时不替换拥有
该环境的 SV 结构时，使用此示例。

`BaseDriver` 在 SystemVerilog 中声明。`PythonDriver` 从它生成的 Python
mirror 派生，校验 constructor 参数并重载 timed `drive` task。SV 使用正常
base type 构造生成 proxy 并调用 `drive`；调用到达 Python override，并通过
`svx.delay` 推进仿真时间。

## 生成镜像

manifest 是唯一运行时 contract。编译 testbench 前生成 Python 和 SV adapter：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest examples/cross_language_inheritance/inheritance.json \
  --python-out examples/cross_language_inheritance/generated/python \
  --sv-out examples/cross_language_inheritance/generated/inheritance_mirrors.sv \
  --artifact-manifest examples/cross_language_inheritance/generated/svx-artifacts.json
```

编译带有生成 SV mirror 的 `tb.sv`，并让仿真进程能够看到
`generated/python` 和仓库 Python root。testbench 加载 `python_checks.py`，它从
生成 mirror package 导入 `svx_sv.example_driver_pkg.BaseDriver`。

## 可复用原则

- 保持 base class 和既有 SV ownership model 在 SV 中。
- 在 manifest 中声明每个跨边界 method、direction、timing class 和 SvTypes value type。
- 从生成 mirror 派生 Python implementation，保留 foreign class 和 method 的同名形式。
- 让声明的 initiator 独占构造；本例使用 SV initiator。
- 仿真结束时调用 `svx_shutdown()`，释放全部 mirror pair。

应用代码不得直接调用生成 dispatcher 或 raw inheritance binding。manifest 变化后
重新生成 mirror；在构建 gate 中使用 `inheritance-gen --check` 拒绝陈旧产物。
