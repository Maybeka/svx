# UVMX Peer Test Selection

This temporary U0 example proves that one ordinary UVM selection path can
choose either a pre-existing SystemVerilog test or an opt-in Python test.
It is intentionally outside the published SVX package.

The Python declaration in `python_tests.py` generates `py_smoke_test`, a
normal SV `uvm_test` subclass.  The same top-level also provides
`legacy_sv_test`.  Select either with the standard UVM spelling:

```text
+UVM_TESTNAME=legacy_sv_test
+UVM_TESTNAME=py_smoke_test
```

For the Python case, the generated proxy creates the Python object during UVM
factory construction, forwards `build_phase` and `run_phase`, holds a UVM
objection while the Python `run_phase` runs, and receives one typed SvTypes
transaction in the SV monitor supplied by `uvmx_python_base`.

The generator delegates callback transport to the public
`svx.callbacks.CallbackAdapter` interface. UVMX controls only UVM test
registration, phase forwarding and objections; it does not hand-author SVX
object IDs, call records or DPI bridges.

For a standalone source checkout, add `uvmx/python` and this example directory
to Python's import path. Build against the SV support files returned by
`svx native-source` and `svtypes.sv_runtime_file()`, and add `uvmx/sv` to the SV
include path. When the simulator embeds Python, its import path must also
contain the installation's Python package directory.

From a directory containing the standalone `uvmx` source tree, generate the
example's adapters with installed SVX/SvTypes:

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
