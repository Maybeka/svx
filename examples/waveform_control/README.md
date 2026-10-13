# Optional Waveform Control

[中文](README.zh-CN.md)

Run [python_test.py](python_test.py) from [tb.sv](tb.sv). The SV DUT keeps
running while Python controls when and where waveform data is recorded.
No manifest, generated mirror, or user-written wave wrapper is required.

## Setup

Follow the [shared run guide](../RUNNING_EXAMPLES.md). Build `libsvx` with direct
hierarchical access enabled (`SVX_REQUIRE_DIRECT_VPI=ON` and the matching
`SVX_SIMULATOR_INCLUDE_DIR`). Load an FSDB dumping backend in the simulation
build and define the SV preprocessor macro `SVX_ENABLE_FSDB_WAVEFORM` before
compiling `svx_pkg`. The optional wrapper is included by `sv/svx_pkg.sv` and
ships with SVX; external dumper libraries are not bundled.

First compile the optional wrapper with the installed backend to check that its
system tasks are supported. A runtime branch cannot hide an unknown system
task from compilation. Without the macro, ordinary SVX remains available and
`svx.waveform.capabilities()` returns an empty set. Importing `svx` in a normal
Python process does not start or load a waveform backend.

Compile `examples/waveform_control/tb.sv` with the usual SVX and SvTypes include
roots. Make the checkout importable (`PYTHONPATH=python:../svtypes/python:.`),
load `libsvx`, and set `SVX_WAVEFORM_OUTPUT` to a fresh writable output directory.
The Python module creates the directory; the API itself does not create missing
parent directories. Existing or previously used filenames are rejected.

## Recording Sequence

```python
wave = svx.waveform
wave.begin("first.fsdb", scopes=[("tb.dut", 1)])
wave.pause()
wave.resume()
wave.switch_file("continued.fsdb")
wave.add_scope("tb.dut.child", 0)
wave.finish()
wave.begin("second.fsdb", scopes=[("tb.dut.child", 0), ("tb.other", 0)])
wave.finish()
```

These calls run synchronously in an SVX simulator-owned task context and do not
advance simulation time. Use `svx.delay()` between them when recording separate
time intervals. They are rejected in SV function callbacks. Scope strings are
resolved at the call; they do not require `Signal` declarations. All scopes in
`begin` are validated before any file is opened. Depth1 selects the scope,
depth2 includes one child level, and depth0 includes all descendants.

Expected result is `WAVEFORM_CONTROL_PASS` and three FSDB files:

- `first.fsdb`: parent counter from0 to15ns, with5..10ns paused.
- `continued.fsdb`: same selection from15ns, plus the child added at15ns.
- `second.fsdb`: fresh child/other selection from25 to30ns, without parent count.

Validate signal names and value-change intervals, not just file existence.
Paused history and history before adding a scope are not reconstructed.

## Boundaries

`switch_file` preserves the selection. `finish` closes all FSDB outputs, resets
selection, and allows a fresh `begin`. It is idempotent. `pause` and `resume` are
also idempotent in their respective active states. `add_scope` only adds signals;
it cannot remove an existing selection. `flush` writes buffers but does not close.

The API owns a single global dumping session. Do not mix it with independent SV
or Tcl dump control, because the backend's close/on/off operations can affect all
files. Missing/unsupported scopes, invalid state and filename errors raise
`SVXWaveformError`; runtime ownership errors raise `SVXContextError`. A successful
call does not certify every internal dumper or disk-I/O error: retain backend
diagnostics and check the output. Call `finish` before `svx_shutdown`.
