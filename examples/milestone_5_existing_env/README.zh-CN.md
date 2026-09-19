# 既有 SystemVerilog 环境

[English](README.md)

在既有 SystemVerilog 环境中采用 SVX，同时不引入新的 SVX component framework
时，使用此模式。

硬件相关行为仍在 SystemVerilog：

- `existing_style_driver()` 消费 typed request 并驱动 toy bus 信号。
- `existing_style_monitor()` 采样 toy bus 并发布 observation。
- Python 在 `tests/integration_test.py` 中负责测试意图和检查。

示例使用稳定的启动和 channel API：

- `svx_init`、`svx_load` 和 `svx_start`
- 具名 payload channel
- SvTypes typed payload metadata 和 bytes
- 从 Python SvTypes model 生成的 SystemVerilog class
- 同步 Python export；不使用 Python `async` 或 host thread

生成 SystemVerilog model：

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_5_existing_env.tests.types \
  --channel-helpers \
  --out examples/milestone_5_existing_env/generated_types.sv
```

通过目标仿真器的正常 DPI flow 集成 `tb.sv` 和
`tests/integration_test.py`。定义 `SVX_M5_CHECKER_FAILURE` 可执行故意的
checker failure；输出应包括 `AssertionError: response data mismatch` 和
`SVX FATAL`，请检查输出而非依赖进程退出码。

此示例不是 verification-flow adapter framework，而是展示当前 SVX 如何连接
传统 SV testbench 的迁移模式。
