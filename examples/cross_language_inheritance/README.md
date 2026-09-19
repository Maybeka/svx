# Cross-Language Inheritance

[中文](README.zh-CN.md)

Use this example when an existing SystemVerilog virtual base class should gain
a Python implementation without replacing the SV environment that owns it.

`BaseDriver` is declared in SystemVerilog. `PythonDriver` derives from its
generated Python mirror, validates the constructor argument, and overrides the
timed `drive` task. SV constructs the generated proxy using the normal base
type and invokes `drive`; the call reaches the Python override and advances
simulation time through `svx.delay`.

## Generate Mirrors

The manifest is the sole runtime contract. Generate its Python and SV adapters
before compiling the testbench:

```sh
PYTHONPATH=python:../svtypes/python:. python -m svx inheritance-gen \
  --manifest examples/cross_language_inheritance/inheritance.json \
  --python-out examples/cross_language_inheritance/generated/python \
  --sv-out examples/cross_language_inheritance/generated/inheritance_mirrors.sv \
  --artifact-manifest examples/cross_language_inheritance/generated/svx-artifacts.json
```

Compile `tb.sv` with the generated SV mirror, then make both
`generated/python` and the repository Python roots visible to the simulator
process. The testbench loads `python_checks.py`, which imports
`svx_sv.example_driver_pkg.BaseDriver` from the generated mirror package.

## What To Reuse

- Keep the base class and any existing SV ownership model in SV.
- Declare each crossing method, direction, timing class, and SvTypes value type
  in the manifest.
- Derive the Python implementation from the generated mirror with the same
  foreign class and method names.
- Let the declared initiator own construction. This example uses SV initiation.
- Call `svx_shutdown()` at simulation teardown to release all mirror pairs.

Do not call generated dispatchers or raw inheritance bindings from application
code. Regenerate mirrors whenever the manifest changes, and use
`inheritance-gen --check` in a build gate to reject stale output.
