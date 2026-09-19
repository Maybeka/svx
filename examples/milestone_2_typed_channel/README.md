# Typed Channel Fundamentals

[中文](README.zh-CN.md)

This focused example introduces the SvTypes typed channel layer on top of raw
binary payload channels:

- Python packs a generated `SvObject` transaction and sends it through
  `Channel.put(...)`.
- SV receives and checks the unified type name, encoding fingerprint, and binary
  format version before unpacking the generated transaction class.
- SV sends the same generated type through its typed channel helper.
- Python receives it with `Channel.get(M2Transaction)` and unpacks it with
  SvTypes checked decode.
- Python rejects a typed payload whose `type_name` metadata does not match the
  requested transaction class.

`generated_types.sv` is reproducible from the Python declaration with:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx svtypes-gen \
  --module examples.milestone_2_typed_channel.tests.typed_test \
  --package m2_typed_pkg \
  --channel-helpers \
  --out examples/milestone_2_typed_channel/generated_types.sv
```

The transaction payload is never hex-encoded for transport.

For a clocked driver, monitor, request/response channels, and generated helpers,
continue with the [typed bus example](../milestone_7_sv_typed_helpers).
