# Typed Channel 基础

[English](README.md)

此专项示例介绍建立在 raw binary payload channel 上的 SvTypes typed channel 层：

- Python 对生成的 `SvObject` transaction 编码后用 `Channel.put(...)` 发送。
- SV 在解码生成的 transaction class 前检查统一类型名、编码 fingerprint 和
  binary format version。
- SV 通过 typed channel helper 发送同一生成类型。
- Python 用 `Channel.get(M2Transaction)` 接收，并由 SvTypes checked decode 解码。
- Python 拒绝 `type_name` metadata 与请求 transaction class 不匹配的 typed payload。

`generated_types.sv` 可由 Python declaration 确定性生成：

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx svtypes-gen \
  --module examples.milestone_2_typed_channel.tests.typed_test \
  --package m2_typed_pkg \
  --channel-helpers \
  --out examples/milestone_2_typed_channel/generated_types.sv
```

transaction payload 在传输中不会被 hex 编码。

若需要时钟化 driver、monitor、request/response channel 和生成 helper，请继续
阅读 [typed bus 示例](../milestone_7_sv_typed_helpers/README.zh-CN.md)。
