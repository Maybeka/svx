# Typed Bus Testbench

[English](README.md)

这是推荐的首个端到端 SVX 示例。它在 SystemVerilog 中保留时钟化 driver 和
monitor，而 Python 负责 transaction program 和检查。生成的 SystemVerilog
typed-channel helper 在两个方向传输 SvTypes object。

它使用：

- `python -m svx svtypes-gen --channel-helpers`
- Python typed role helper
- 如 `svx_get_M7BusReq` 和 `svx_put_M7BusRsp` 的生成 SV helper
- testbench 中不手写 SV payload metadata 校验
- testbench 中不手写 SV payload-to-byte-queue unpack 样板代码

生成 SystemVerilog model 和 helper：

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_7_sv_typed_helpers.tests.types \
  --channel-helpers \
  --out examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv
```

通过目标仿真器的正常 DPI flow 集成 `tb.sv` 和生成 helper 文件。

预期失败 testbench `tb_type_mismatch.sv` 验证生成的 `svx_get_T` helper 在
channel/type metadata 不匹配时，报告 helper 名、channel 名、期望类型和实际
metadata。

随后可阅读 [跨语言继承](../cross_language_inheritance/README.zh-CN.md) 了解
virtual class override，或阅读 [分层信号访问](../hierarchical_signal_access/README.zh-CN.md)
了解目标化 setup 与 fault injection。
