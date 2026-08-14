# SVX Milestone 5 Existing-Environment Example

This example demonstrates the active M5 direction: introduce current SVX into
an existing-style SystemVerilog environment without adding a new SVX component
framework.

The test keeps hardware-facing behavior in SystemVerilog:

- `existing_style_driver()` consumes typed requests and drives a toy bus signal
  set.
- `existing_style_monitor()` samples the toy bus and publishes observations.
- Python owns the test intent and checking in
  `tests/integration_test.py`.

The example uses current M1-M4 primitives only:

- `svx_init`, `svx_load`, and `svx_start`
- named payload channels
- SvTypes typed payload metadata and bytes
- generated SystemVerilog classes from Python SvTypes models
- synchronous Python exported function; no Python `async` or host threading

Generate the SystemVerilog model:

```sh
PYTHONPATH=python:. python3 -m svx svtypes-gen \
  --module examples.milestone_5_existing_env.tests.types \
  --channel-helpers \
  --out examples/milestone_5_existing_env/generated_types.sv
```

Integrate `tb.sv` and `tests/integration_test.py` with the target simulator's
normal DPI flow. Define `SVX_M5_CHECKER_FAILURE` to exercise the intentional
checker failure. The failure reports `AssertionError: response data mismatch`
and `SVX FATAL`; inspect the output rather than relying on an exit code.

This example is intentionally not a verification-flow adapter framework. It is
a migration pattern showing where current SVX can connect to a conventional SV
testbench.
