# Register Lab

[中文](README.zh-CN.md)

This four-register peripheral ties transactions, processes, both inheritance
directions, fields, handles, signal diagnostics and callbacks to one real DUT.
Normal and fault cases are separate. The core project does not depend on UVM.

## Current Flow

`models.py` defines SvTypes request/response/observation records. `generate.py`
produces their SV models and channel helpers. `tb.sv` owns reset, clock, a real
`dut.sv`, a bus driver and an independently clocked monitor. `scenarios.py`
forks a Python producer and scoreboard, sharing an expected-value dictionary.

The smoke case writes four registers and reads them back: eight requests,
eight responses and eight independent observations. A background watchdog
demonstrates cleanup on kill; a short race demonstrates join-any and stopping
the remaining child. Diagnostic signal access is limited to a cookie/status
and a separately selected fault case, never used as the bulk bus transport.

## Generate And Compile

From the SVX repository root, with SVX and SvTypes installed in a compatible
Python environment:

```sh
python -m examples.register_lab.generate
python -m examples.register_lab.generate --check
svx sv-files
svx compile-flags
svx libs
```

Compile `examples/register_lab/tb.sv`; it includes the DUT, interface, generated
models and support packages. Provide the repository root and SvTypes runtime SV
directory as include paths. Load the matching SVX native library and expose
the project root plus installed Python packages to the simulator's embedded
Python. The native library and simulator must enable direct hierarchical
signal access, as described in the shared [running guide](../RUNNING_EXAMPLES.md).

Generation includes SvTypes models, Python/SV source discovery, an inheritance
manifest, mirrors/proxies, restricted VIF views, an artifact manifest and the
callback-only Report. Install `pyslang` and SVX's runtime dependencies; the
embedded interpreter must find them. Besides installed or development paths,
the simulation process requires:

```sh
export PYTHONPATH="$PWD/examples/register_lab/generated/python:$PWD:${PYTHONPATH:-}"
export SVX_ARTIFACT_MANIFEST="$PWD/examples/register_lab/generated/svx-artifacts.json"
```

Source development also includes `python` and `../svtypes/python`. `--check`
never repairs output. Regenerate without it when stale; do not edit generated code.

## Cases And Expected Results

- Default / `+LAB_CASE=smoke`: emits `REGISTER_LAB_SIGNALS_PASS`,
  `REGISTER_LAB_PROCESSES_PASS`, `REGISTER_LAB_BUS_PASS transactions=8 observations=8`,
  `REGISTER_LAB_PAYLOAD_PASS`, `REGISTER_LAB_PYTHON_PASS` and finally
  `REGISTER_LAB_PASS case=smoke`, with no failure diagnostics.
- `+LAB_CASE=corrupt_read`: forces read data to zero. The scoreboard must report
  `REGISTER_LAB_MISMATCH` and terminate through SVX fatal policy; no final pass
  marker is allowed. A zero process exit code alone does not qualify this case.
- `+LAB_CASE=function_wait`: deliberately call `svx.delay()` inside a function
  callback. Reject it before time advances; require `svx.delay() is not allowed`,
  `Checker#compare` and `SVX FATAL`, with no normal return or final pass marker.

Normal flow additionally requires `REGISTER_LAB_POLICY_CREATED`,
`REGISTER_LAB_SV_CALLBACK_PASS`, `REGISTER_LAB_HANDLES_PASS`,
`REGISTER_LAB_CHECKER_PASS`, `REGISTER_LAB_POLICY_CLOSE_PASS`,
`REGISTER_LAB_REPORT_FUNCTION_PASS` and `REGISTER_LAB_REPORT_TASK_PASS`.
Negative cases must also reject timeout/crash: arbitrary failure is not success.

The process checks also emit `REGISTER_LAB_INDEPENDENT_WAITS_PASS`: completing
get/peek on one channel must not release a waiter on another channel, and peek
must preserve its data. Only the fast child may finish the short race; the
remaining child is stopped with `kill_running()`, not returned early as a success.

Normal bulk access stays in clocked SV. The Python test advances simulation
time only through SVX; it does not use threads, async or wall-clock sleeps.

## Files

| File | Responsibility |
|---|---|
| `dut.sv`, `register_if.sv` | peripheral and bus wiring |
| `tb.sv` | lifecycle, clock/reset, driver, monitor, trace echo |
| `models.py`, `generated/models.sv` | sole typed transaction contract |
| `scenarios.py` | scenarios, scoreboard, process and payload checks |
| `signals.py` | paths validated during runtime initialization |
| `generate.py` | generate/check declared build inputs |
| `policy_types.sv`, `extensions.py` | SV base, Python policy, parameter directions, external handles |
| `checker.sv`, `extensions.py::Checker` | SV derives Python, function/task and super |
| `reporting.py`, `generated/report.sv` | public callback adapter function/task integration |

## Project Walkthrough

1. Read `models.py`, `register_if.sv` and `dut.sv`: one typed contract and four
   32-bit registers at addresses 0/4/8/12.
2. Read the `tb.sv` initial block: reset, declared-signal validation, factory
   registration, Python entry and shutdown. The simulator owns time and processes.
3. Follow `check_processes` and `check_independent_waits`, then `check_bus`.
   Producer and scoreboard share Python expectation objects, not execution stacks.
4. The SV driver waits for stable data; the monitor samples independently.
   Requests/responses cannot substitute for observations. `lab.env.done` waits for
   driver/monitor/trace completion before teardown.
5. Follow both inheritance paths below, then diagnostic signals, raw trace and Report.

### Python Derives SV

`RegisterPolicyStub` is an empty discovery declaration. Source scanning resolves
the base from `policy_types.sv`; the artifact manifest binds the generated
`svx_mirror.register_policy_pkg.RegisterPolicy`. `PythonPolicy(mask)` creates its
paired SV instance without an application-assigned object ID.

Both producer and SV driver call `normalize`. The SV base handle dispatches
virtually to Python; `super().normalize(...)` invokes the SV base implementation.
`mask`, `calls` and `history` reside in SV; the new SvTypes `local_checks` remains
Python-local for this target. Scalars use `.value`, Queue uses
`history.push_back(...)`. Both sides together make 16 calls and history is 1..16.
After close, SV fields are invalid while Python-local fields remain readable.

Both languages call `calibrate`, preserving Input/Output/Inout positions.
Python changes carrier `.value` and returns the ordinary result separately;
SVX handles encoding and copy-out. `word_bytes()` shows static dispatch.
The experimental `publish_object` / `SVX_GET_OBJECT` explicitly hands off a live,
bound object; it is not reflection or ownership transfer.

### SV Derives Python

The source `Checker` defines comparison logic. SV `RegisterChecker` derives from
the generated `svx_proxy_extensions::Checker`. Registering
`CheckerFactory#(RegisterChecker)` selects this implementation when Python creates
`svx_py.examples.register_lab.extensions.Checker(42)`. This single implementation
selector does not replace source-integrated generation of complete alternating lineages.

`checker.compare(...)` enters the SV override, whose `super.compare(...)` calls
the Python base. `finish` waits first in SV, then in Python through `svx.delay`,
remaining one synchronous task chain. `Bit[1]` renders as `bit [0:0]`; a
handwritten override must match it, not substitute scalar `bit`.

### Handle Permissions

PacketTag is not a generation target. Python's opaque `RemoteRef` can be retained
and returned with identity preserved, but cannot expose `number`. The static
`register_if.diagnostics` modport exposes `read_address()`, `read_rdata()` and
`read_data()` with no bus writes. Passing its view back to `same_bus(view)` uses
native SV comparison to verify identity. Do not inspect private generated IDs.

## Iterate

- Transaction fields, method prototypes, projected fields or SV declarations
  changed: rediscover, regenerate and recompile SV.
- Python method body changed: still run `generate --check`, refreshing its input
  record when requested. Unchanged bridge content need not be recompiled. See the
  [incremental workflow](../../docs/SVX_USER_MANUAL.md#21-iterative-development).
- Transaction counts changed: update driver/monitor bounds and checker expectations.
- `tests/python/test_register_lab_generation.py` uses isolated outputs to check
  missing-file rejection without repair and recovery by regeneration, and verifies
  PacketTag receives no unwanted mirror.

## Optional UVM Launch

The source-only `incubator/uvmx/examples/register_lab` reuses this project and
selects Python-defined and SV-defined Tests through the same UVM factory's
`+UVM_TESTNAME`. Its bilingual READMEs describe setup and expected results. This
temporary adapter is not exported in the SVX package, is not a core dependency,
and does not promise deep UVM class mapping.
The adapter also includes `register_lab_extended_test`, a Python subclass with
its own state and an additional build callback. Python tests are registered at
startup, not emitted as individual SV classes. After the initial build, adding
a decorated test using an already compiled SV base requires only a simulator
restart with its new `+UVM_TESTNAME`; do not regenerate or recompile SV.
