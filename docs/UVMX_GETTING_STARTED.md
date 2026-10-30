# Prepare And Use UVMX

[中文](UVMX_GETTING_STARTED.zh-CN.md)

This guide assumes UVM already runs in your project and SVX, SvTypes, their SV
packages and the native runtime are ready. It adds a Python Test while retaining
ordinary UVM `run_test()` and `+UVM_TESTNAME` selection for both test origins.

Start with the built-in `uvm_test` base. **No per-test SV class or UVMX base
registration generation is needed.** Generation is added only for an uncompiled
custom SV base or a new SV-facing data contract.

## 1. Obtain Source And Configure Imports

UVMX currently lives in the SVX checkout at `incubator/uvmx`. It is not included
in the SVX distribution, so installing SVX alone is insufficient. Obtain this
source tree; do not use `pip install uvmx` for this prototype.

From your project directory, replace the first path:

```sh
export UVMX_ROOT="/path/to/svx/incubator/uvmx"
export PROJECT_ROOT="$PWD"
export PYTHONPATH="$UVMX_ROOT/python:$PROJECT_ROOT:${PYTHONPATH:-}"
python -c 'import svx, svtypes, uvmx; print("UVMX_IMPORT_OK")'
```

Preserve the existing SVX/SvTypes import configuration. The simulator's embedded
Python must receive the same paths. Successful shell imports alone do not prove
simulation works; `UVMX_IMPORT_OK` is only an import check.

## 2. Define A Default-Base Test

Create `my_tests.py` in the project directory:

```python
"""Default-base UVMX startup without generated test or base registrations."""

import svx
from uvmx import Test, uvm_test


@uvm_test(
    canonical_id="py://verification/SmokeTest",
    factory_name="python_smoke",
)
class SmokeTest(Test):
    def run_phase(self):
        svx.display("UVMX_MINIMAL_START")
        svx.delay(2, "ns")
        svx.display("UVMX_MINIMAL_PASS")
```

Omitting `sv_base` selects the built-in `uvm_pkg::uvm_test`. Methods execute
synchronously, without async/await. This example declares no new transactions,
so it also needs no `svtypes-gen` step. It proves startup and synchronous timing,
not automatic environment construction or mapping.

## 3. Keep The Native UVM Entry

Create a minimal `tb.sv`, or apply this sequence to the single existing launcher:

```systemverilog
module tb;
  timeunit 1ns;
  timeprecision 1ps;

  initial begin
    uvmx_pkg::uvmx_init("my_tests");
    uvm_pkg::run_test();
  end
endmodule
```

Initialization imports the entry and its imports and returns after all decorated
tests have been registered in the original UVM factory. Do not race registration
and run_test in separate initial blocks or keep a second run_test call. There is
no additional manual svx_init or Python test entry to start.

UVMX leaves finish_on_completion unchanged. Native UVM normally finishes the
simulation, so do not rely on statements after run_test for cleanup. Applications
choosing return mode can call the existing svx_shutdown before exiting. It is a
task and cannot be called from final.

## 4. Compile The Fixed Support Once

Retain your existing UVM configuration, SvTypes/SVX inputs and native library:

| Order | Input | Action |
|---|---|---|
| 1 | Original UVM configuration or package | Retain the existing setup; do not compile an implicitly loaded package twice |
| 2 | SvTypes and SVX packages | Reuse the ready inputs; `svx sv-files` locates them |
| 3 | `$UVMX_ROOT/sv/uvmx_pkg.sv` | Add to the compilation inputs |
| 4 | Existing environment, SV tests and user top | Keep existing tests and replace the single launch sequence |

Add `$UVMX_ROOT/sv` to the SV include paths, retaining the original UVM macros,
SVX and SvTypes paths. The UVMX package already includes its registration,
callbacks, factory and initialization files; do not compile those includes as
separate units. Keep loading the existing working SVX native library; this
default-base test does not require rebuilding it.

The minimal route has no custom-base registration package or user transaction
package. **Do not run uvmx_gen.py or add an extra uvmx_generated_pkg import.**
The complete minimal sources are in `incubator/uvmx/examples/minimal_test`.

## 5. Select Tests And Iterate In Python

Append to your normal simulation invocation:

```text
+UVM_TESTNAME=python_smoke
```

Expect `UVMX_MINIMAL_START`, a synchronous 2 ns wait and `UVMX_MINIMAL_PASS`, with
no UVM/SVX errors. Select an existing SV test using its original UVM_TESTNAME.

The minimal sources were simulator-qualified on 2026-10-30 using only the fixed
packages and top, no generators and an existing native library. Completion was
at 2 ns, with zero UVM warnings, errors and fatals.

The entry module may contain many tests or only aggregate imports:

```python
from verification.smoke import SmokeTest
from verification.reset import ResetTest
```

Each imported test uses @uvm_test and a unique factory_name. Unimported files are
not scanned. New Python tests, state, algorithms and supported phase overrides
reuse the same executable when the compiled bases and data contracts stay
unchanged. Do not rerun a generator or compiler; restart with the new name. This
is startup loading, not hot-loading into an active simulation.

## 6. Optional Custom Bases And Transactions

To retain an existing SV test base that creates an environment, select it:

```python
@uvm_test(
    canonical_id="py://verification/SmokeTest",
    factory_name="python_smoke",
    sv_base="env_pkg::EnvBaseTest",
)
class SmokeTest(Test):
    def run_phase(self):
        ...
```

The prototype currently requires this base to directly extend uvm_test. Generate
its registration once, when first adding that base:

```sh
python "$UVMX_ROOT/tools/uvmx_gen.py" \
  --module my_tests \
  --sv-base-source verification/env_base_test.sv \
  --sv-out generated/uvmx_bases.sv \
  --artifact-manifest generated/uvmx_artifacts.json
```

Compile env_pkg and generated/uvmx_bases.sv after the UVMX package and before
the top, and import uvmx_generated_pkg in the top. Generation covers distinct
SV bases, not individual Python test classes. Additional tests reusing the same
base need no generation or compilation. Choosing a base does not automatically
expose its members to Python: connect actual transaction services through
explicit SVX class mapping or SvTypes channels.

| Change | Additional generation |
|---|---|
| Default uvm_test, no new SV-facing transactions | None |
| New Python test using compiled bases and data contracts | None |
| Previously uncompiled custom SV Test base | Generate and compile its base registration |
| New or changed SvTypes transactions consumed by SV | Follow the normal SVX data/channel generation and compilation flow |

Continue with the source examples in incubator/uvmx/examples/peer_test_selection
and incubator/uvmx/examples/register_lab. Their custom-base or typed-transaction
generation is specific to those examples, not mandatory for minimal startup.
