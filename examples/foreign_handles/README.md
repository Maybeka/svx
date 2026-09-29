# Foreign Class Handles and Virtual Interfaces

[中文](README.zh-CN.md)

This example has two deliberately different foreign-handle boundaries.

- `Packet` is an arbitrary SV class. Python receives its SvTypes `RemoteRef`,
  retains it, and returns it without object construction or member access.
  The SV caller receives the same base-class handle, including the dynamic
  `TaggedPacket` instance.
- `virtual example_bus_if.master` becomes the generated Python class
  `svx_vif.example_bus_if.master.Master`. Its methods are derived from the
  modport: `write_data`, `write`, and `read`. No separate Python access list
  is maintained.

For common build inputs, runtime loading, and pass/fail expectations, see the
[example run guide](../RUNNING_EXAMPLES.md).

## Generate

The manifest names the one requested Python endpoint. The foreign handle
adapters and VIF view are dependencies discovered from its declarations.

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-manifest \
  --python-module examples.foreign_handles.python_api \
  --sv-source examples/foreign_handles/bus_if.sv \
  --out examples/foreign_handles/generated/handles.json

PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest examples/foreign_handles/generated/handles.json \
  --sv-source examples/foreign_handles/bus_if.sv \
  --python-out examples/foreign_handles/generated/python \
  --sv-out examples/foreign_handles/generated/mirrors.sv \
  --artifact-manifest examples/foreign_handles/generated/svx-artifacts.json
```

The VIF discovery step requires the optional manifest frontend dependency.
Install SVX with its `manifest` extra on the machine that performs generation.

## Run

Compile `tb.sv`, the SvTypes SV runtime package, `svx_pkg.sv`, and
`generated/mirrors.sv` through the normal SVX DPI integration. Add
`examples/foreign_handles/generated/python`, `python`, and the project root
to `PYTHONPATH` when running the simulation.

`tb.sv` verifies the class handle's dynamic-instance identity, Python VIF
signal write/function access, and the returned VIF's continued SV usability.

See [the handle-adapter contract](../../docs/CROSS_LANGUAGE_HANDLE_ADAPTERS.md)
for lifecycle, null, and unsupported-operation rules.
