# Optional UVM Launch For Register Lab

[中文](README.zh-CN.md)

This temporary UVMX adapter reuses the [core register project](../../../../examples/register_lab/README.md)
without changing its data, driver, monitor or inheritance implementation. The
core does not import UVMX or require UVM. This directory is source-development
only; the incubated UVMX has not yet been extracted into a separate project.

## Generate And Compile

Generate and build the core project first. Add `incubator/uvmx/python` to the
Python import path, then generate the reusable base-registration package from the repository root:

```sh
export PYTHONPATH="$PWD/incubator/uvmx/python:$PWD/examples/register_lab/generated/python:$PWD:${PYTHONPATH:-}"
python incubator/uvmx/tools/uvmx_gen.py \
  --module incubator.uvmx.examples.register_lab.python_test \
  --package register_lab_uvmx_pkg \
  --sv-out incubator/uvmx/examples/register_lab/generated/tests.sv \
  --artifact-manifest incubator/uvmx/examples/register_lab/generated/artifacts.json
```

Keep the core `SVX_ARTIFACT_MANIFEST` and native-library loading configuration.
Compile this directory's `tb.sv` instead of the core top, providing the UVM
package, macros and `incubator/uvmx/sv` include path. Use a consistent default
1 ns / 1 ps time setting and the core's required signal-access configuration.
Do not compile both tops: this entry includes and reuses the core top.

## Peer Selection

- `+UVM_TESTNAME=register_lab_python_test`: the UVM factory selects the Python Test.
- `+UVM_TESTNAME=register_lab_extended_test`: selects `PythonExtendedTest(PythonTest)`,
  with Python-only instance state, a build callback and Python `super()` reuse.
- `+UVM_TESTNAME=register_lab_sv_test`: the same factory selects the SV Test in `legacy_test.sv`.

Both run phases execute the same register smoke. Require `REGISTER_LAB_UVMX_PASS`
for the Python definition, or `REGISTER_LAB_UVM_PASS` for the SV definition.
Both require `REGISTER_LAB_CHECKER_PASS`, `REGISTER_LAB_POLICY_CLOSE_PASS` and
`REGISTER_LAB_PYTHON_PASS`, with no UVM/SVX errors.
The extended case additionally requires `REGISTER_LAB_UVMX_EXTENDED_BUILD_PASS`
and `REGISTER_LAB_UVMX_EXTENDED_PASS`.

The SV Test uses SVX to launch the same Python scenario; this does not move the
UVM scheduler into Python. Only Test and synchronous phase callbacks are mapped.
UVM still owns factory, phases, objections and exit. `run_test()` starts at time
zero while an independent SV reset process runs; driver/monitor wait for reset.
The scenario waits for all three environment completion notifications before
ending, then the launcher shuts down before simulator exit. It therefore does
not depend on the core top's post-UVM join or report code.

Deep UVM class mapping and full Python UVM compatibility are outside this example.

Python declarations are loaded and their factory names registered before
`run_test()`, not compiled into
per-test SV classes. After this build, add another decorated Python Test using
the default base, then launch its new name with `+UVM_TESTNAME` using the same
binary and native library. No SV regeneration is needed for the new Python test.
The class must be imported by the module passed to the launcher before startup
registration; restarting the executable reloads Python, not the compiled SV.
Only a new SV base or an altered SV-facing data contract needs an SV rebuild.
