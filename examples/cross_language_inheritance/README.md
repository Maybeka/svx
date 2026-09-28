# Cross-Language Inheritance

[中文](README.zh-CN.md)

Follow the common [example run guide](../RUNNING_EXAMPLES.md) before compiling this example.

Use this example when an existing SystemVerilog virtual base class should gain
a Python implementation without replacing the SV environment that owns it.

`BaseDriver` is declared in SystemVerilog. The manifest records the complete
`BaseDriver (SV) -> PythonDriver (Python)` lineage. Generation exposes
`svx_mirror.example_driver_pkg.BaseDriver` as the Python base class. Its SV
counterpart is the implementation-only derived type
`svx_mirror_sv_example_driver_pkg_BaseDriver::BaseDriver`. Python constructs
`PythonDriver`; SVX creates and binds that bridge automatically. Python then
explicitly publishes it as `example.driver`. SV obtains it as an ordinary
`example_driver_pkg::BaseDriver` handle and calls `drive`, so the call reaches
the Python override and advances simulation time through `svx.delay`.

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
`svx_mirror.example_driver_pkg.BaseDriver` from the generated mirror
package.

## What To Reuse

- Keep the base class and any existing SV ownership model in SV.
- Declare each crossing method, direction, timing class, and SvTypes value type
  in the manifest.
- Derive the Python implementation from the generated same-name mirror.
- Put the complete SV ancestor declaration in the Python target's
  `base_lineage`; this is context, not a request to generate a second base.
- Let the declared initiator own construction. This example uses Python
  initiation: `PythonDriver()` creates the paired SV object.
- `svx.publish_object("example.driver", driver)` explicitly hands a live
  object to SV. Use `` `SVX_GET_OBJECT(ExpectedType, name, target) `` in SV;
  it validates the recovered object with `$cast` before assignment.
- Call `svx_shutdown()` at simulation teardown to release all mirror pairs.

Do not call generated dispatchers or raw inheritance bindings from application
code. In particular, application SV code must not declare or construct the
implementation-only bridge type. Regenerate mirrors whenever the manifest changes, and use
`inheritance-gen --check` in a build gate to reject stale output.
