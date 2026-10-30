# UVMX Peer Test Selection

[中文](README.zh-CN.md)

Start with [Prepare And Use UVMX](../../../../docs/UVMX_GETTING_STARTED.md).
The default uvm_test route needs no base registration generator. This example
additionally uses a custom SV base and typed transactions; the generation below
is for those additional contracts, not a mandatory step for all UVMX users.

This temporary U0 example proves that one ordinary UVM selection path can
choose either a pre-existing SystemVerilog test or an opt-in Python test.
It is intentionally outside the published SVX package.

Complete registration before calling the original UVM task:

```systemverilog
initial begin
  uvmx_pkg::uvmx_init("python_tests");
  uvm_pkg::run_test();
end
```

Initialization loads the entry module and its imports, publishes all declared
Python tests, and returns only when every registration has been consumed. It
does not scan unimported files. Do not race registration with run_test in separate
initial blocks. UVMX neither selects the test nor changes finish_on_completion.
Native UVM normally finishes simulation; if the application configures run_test
to return, it can call svx_shutdown before exiting. That existing shutdown API
is a task and cannot be called from final.

The Python declaration in `python_tests.py` registers `py_smoke_test` at runtime.
It does not generate a corresponding SV test class. The same top-level provides
`legacy_sv_test`.  Select either with the standard UVM spelling:

```text
+UVM_TESTNAME=legacy_sv_test
+UVM_TESTNAME=py_smoke_test
```

For the Python case, a reusable SV bridge creates the Python object during UVM
factory construction, forwards the fixed phase surface, holds a UVM
objection while the Python `run_phase` runs, and receives one typed SvTypes
transaction in the SV monitor supplied by `uvmx_python_base`.
The component constructor keeps the ordinary `new(name, parent)` signature.
The factory wrapper binds Python metadata and creates the Python Test before
returning the component; binding is not delayed until build_phase.

The fixed callback bridge delegates transport to the public
`svx.callbacks.CallbackAdapter` interface. UVMX controls only UVM test
registration, phase forwarding and objections; it does not hand-author SVX
object IDs, call records or DPI bridges.
The adapter selects the registered Python class at runtime and binds the actual
user Test through the existing SVX object factory before initialization. There
is no separate UVMX delegate object or construction/dispatch lifecycle.

For a standalone source checkout, add `uvmx/python` and this example directory
to Python's import path. Build against the SV support files returned by
`svx native-source` and `svtypes.sv_runtime_file()`, and add `uvmx/sv` to the SV
include path. When the simulator embeds Python, its import path must also
contain the installation's Python package directory.

From a directory containing the standalone `uvmx` source tree, generate the
example's data contract and reusable SV-base registration with installed SVX/SvTypes:

```sh
export PYTHONPATH="uvmx/python:uvmx/examples/peer_test_selection${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p generated
python -m svx svtypes-gen --module python_tests --package uvmx_types_pkg \
  --channel-helpers --out generated/uvmx_types.sv
python uvmx/tools/uvmx_gen.py --module python_tests \
  --sv-base-source uvmx/examples/peer_test_selection/base_test.sv \
  --sv-out generated/uvmx_generated.sv \
  --artifact-manifest generated/uvmx_artifact.json
svx native-source
```

Compile the installed SvTypes/SVX support packages, `uvmx/sv/uvmx_pkg.sv`,
`generated/uvmx_types.sv`, the example's `base_test.sv`,
`generated/uvmx_generated.sv`, and the example's `tb.sv`, in that order.
Build/load the SVX native runtime from the installed support sources.

This stage maps test construction and the selected phase callbacks, not the
complete UVM API. Python phase methods take only `self`; their constructor
takes no user arguments. User SV base validation currently accepts a directly
declared `uvm_test` extension. Broader component, field, phase-object and TLM
mapping remains separate work.

The local integration runner is kept separately from these source files.

## Add A Python Test Without Recompiling

After the first build, add a decorated Python `Test` class to `python_tests.py`,
or import it there from another Python module. Use an already-compiled `sv_base`
and a new `factory_name`, then restart the same simulator executable with
`+UVM_TESTNAME=<new factory_name>`. Do not rerun the generator or SV compiler.
Adding an override of any supported phase also requires no SV regeneration.
Existing SV tests remain registered with the same UVM factory and launch path.

The generator emits registrations only for distinct custom SV bases, not for
test names or Python classes. The default `uvm_pkg::uvm_test` bridge is built in.
Only adding a previously uncompiled SV base or changing an SV-facing contract
requires an SV rebuild. Scenario logic, Python fields and transaction processing
stay in Python. Startup publishes typed registration metadata while SV drains it
concurrently, so test count is not limited by channel capacity. Duplicate names,
including collisions with existing SV tests, fail explicitly rather than replace
the original registration.
