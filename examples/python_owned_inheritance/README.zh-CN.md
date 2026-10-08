# Python 所有的跨语言继承

[English](README.md)

编译本示例前，先遵循通用的[示例运行指南](../RUNNING_EXAMPLES.zh-CN.md)。

此示例展示相反的所有权方向：Python 声明 base class 并拥有构造，
SystemVerilog 提供具体 derived class。

`BaseMonitor` 是普通 Python base class；其生成的 SV projection 是
`svx_proxy_base_monitor::BaseMonitor`。`SvCounter` 从该类型派生，重载一个 nonblocking function 和一个
timed task，并在两个方向调用 `super()`。Python 构造 `BaseMonitor(9)` 后，SVX
请求生成的 `BaseMonitorFactory#(SvCounter)` 用相同 constructor 参数创建并绑定 SV partner。

## 生成镜像

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest examples/python_owned_inheritance/inheritance.json \
  --python-out examples/python_owned_inheritance/generated/python \
  --sv-out examples/python_owned_inheritance/generated/inheritance_mirrors.sv \
  --artifact-manifest examples/python_owned_inheritance/generated/svx-artifacts.json
```

使用生成 mirror 编译 `tb.sv`。确保仿真进程既能导入
`examples.python_owned_inheritance.python_test`，也能导入生成的 `svx_py`
package。

manifest 的 top-level target 是 Python `BaseMonitor`，而不是 `SvCounter`。
`tb.sv` 中的用户代码负责让 `SvCounter` 继承生成的
`svx_proxy_base_monitor::BaseMonitor`，启动时创建
`svx_proxy_base_monitor::BaseMonitorFactory#(SvCounter)`。生成的 factory 自动
注册、解码 constructor request，并将 `seed` 传入
`SvCounter.new(object_id, seed)`。应用代码只把收到的 opaque ID 传给
`super.new`，不分配 ID、不解码传输记录，也不调用内部 registry。
本示例为 Python root 选择一个具体 SV 实现，并未声明完整的 Python-root 交替 lineage。

## 验证内容

- Python 发起构造时分配并绑定一个 remote object pair。
- SV factory 以 manifest canonical class ID 注册。
- Python 调用分派至具体 SV override。
- function 和 task 的 `super()` 调用跨回 Python base class。
- `svx_shutdown()` 确定性释放 object pair。

只声明 manifest 支持的方法和值类型，不要手动创建或绑定 remote ID。
