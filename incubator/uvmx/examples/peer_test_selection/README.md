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

The local simulator runner is deliberately kept under `.local-sim/`; it is not
part of the published project.
