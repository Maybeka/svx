# Python-Owned Cross-Language Inheritance

[中文](README.zh-CN.md)

Follow the common [example run guide](../RUNNING_EXAMPLES.md) before compiling this example.

Use this example for the inverse ownership direction: Python declares the base
class and owns construction; SystemVerilog supplies the concrete derived class.

`BaseMonitor` is a normal Python base class. Its generated SV projection is
`svx_proxy_base_monitor::BaseMonitor`. `SvCounter` extends that type, overrides both a
nonblocking function and a timed task, and calls `super()` in each direction.
Python constructs `BaseMonitor(9)`, so SVX asks the registered `SvCounterFactory`
to create and bind the SV partner with the same constructor arguments.

## Generate Mirrors

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest examples/python_owned_inheritance/inheritance.json \
  --python-out examples/python_owned_inheritance/generated/python \
  --sv-out examples/python_owned_inheritance/generated/inheritance_mirrors.sv \
  --artifact-manifest examples/python_owned_inheritance/generated/svx-artifacts.json
```

Compile `tb.sv` with the generated mirror. Ensure the simulator process can
import both `examples.python_owned_inheritance.python_test` and the generated
`svx_py` package.

The manifest's top-level target is Python `BaseMonitor`, not `SvCounter`.
Application SV code makes `SvCounter` extend generated
`svx_proxy_base_monitor::BaseMonitor`,
implements `svx_pkg::svx_factory`, and registers that factory under
`BaseMonitor`'s canonical ID. The factory uses the generated projection constructor
decoder to pass `seed` into `SvCounter.new(object_id, seed)`; application code
never allocates an object ID itself.

## What It Proves

- Python-initiated construction allocates and binds one remote object pair.
- The SV factory is registered under the manifest canonical class ID.
- A Python call dispatches to a concrete SV override.
- Function and task `super()` calls cross back to the Python base class.
- `svx_shutdown()` releases the object pair deterministically.

Only declare methods and value types supported by the manifest. Do not create
or bind remote IDs manually.
