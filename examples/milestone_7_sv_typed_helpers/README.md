# Typed Bus Testbench

[中文](README.zh-CN.md)

This is the recommended first end-to-end SVX example. It keeps a clocked driver
and monitor in SystemVerilog while Python owns the transaction program and
checks. Generated SystemVerilog typed-channel helpers carry the SvTypes
objects in both directions.

It uses:

- `python -m svx svtypes-gen --channel-helpers`
- Python typed role helpers
- generated SV helpers such as `svx_get_M7BusReq` and `svx_put_M7BusRsp`
- no hand-written SV payload metadata validation in the testbench
- no hand-written SV payload-to-byte-queue unpack boilerplate in the testbench

Generate the SystemVerilog model and helpers:

```sh
PYTHONPATH=python:../svtypes/python:. python3 -m svx svtypes-gen \
  --module examples.milestone_7_sv_typed_helpers.tests.types \
  --channel-helpers \
  --out examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv
```

Integrate `tb.sv` and the generated helper file using the target simulator's
normal DPI flow.

The expected-failure testbench `tb_type_mismatch.sv` verifies that generated
`svx_get_T` helpers report channel/type metadata mismatches with helper name,
channel name, expected type, and actual type.

After this example, use [cross-language inheritance](../cross_language_inheritance)
for virtual class overrides or [hierarchical signal access](../hierarchical_signal_access)
for targeted setup and fault injection.
