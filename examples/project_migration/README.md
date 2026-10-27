# Migrate A Pure SV Project To SVX

[中文](README.zh-CN.md)

> Introductory draft, not project-scale end-to-end acceptance. A larger existing
> SV environment is required for that purpose. Unfinished gates are listed below.

Start with a standalone SystemVerilog verification project. Keep the DUT, clock,
reset, driver, and monitor unchanged, then move scenarios, transactions, and
checking into Python in three small changes. Each directory is a runnable
checkpoint, not an incomplete patch to apply over the previous directory.
This is a complete small register project, not a commercial IP migration or a
demonstration of every SVX API.

Follow the shared [run guide](../RUNNING_EXAMPLES.md) for environment and library
setup. After this adoption route, use the [register lab](../register_lab/README.md)
for inheritance, handles, diagnostic signals, and other optional boundaries.

## Target And Invariants

The DUT has four 32-bit registers at addresses `0/4/8/12`, all reset to zero.
Its small `valid/ready` bus inserts zero, one, or two wait cycles according to
the address. It is not a complete implementation of a standard bus protocol.
The driver changes pins at the falling edge; transfers are accepted at the
rising edge when `valid && ready`. Read data is already stable before acceptance.
The independent monitor samples pins, not the driver's response record.

The default program executes 64 uniquely tagged transfers: initial reset reads,
one write to each register, then interleaved reads and overwrites. Both responses
and independently sampled observations are checked.

| Checkpoint | Scenario/transactions | Response checker | Monitor scoreboard |
|---|---|---|---|
| [00_sv](00_sv/tb.sv) | SV | SV | SV |
| [01_entry](01_entry/tb.sv) | SV | SV | SV |
| [02_stimulus](02_stimulus/tb.sv) | Python/SvTypes | Python | SV |
| [03_python](03_python/tb.sv) | Python/SvTypes | Python | Python |

All checkpoints share [the DUT](common/dut.sv), [clock/reset harness](common/harness.svh),
and [BFMs](common/environment.svh). The migration does not introduce a Python
pin driver or a second DUT implementation.

## Build Inputs

Work from the repository root. Use your project's normal compilation, DPI
loading, and log capture flow, selecting one checkpoint's `tb.sv` at a time and
using separate build directories. Do not compile all four `tb` modules together.

| Stage | Additional inputs |
|---|---|
| `00_sv` | Project-root include path only; no SVX library or SvTypes |
| `01_entry` | SVX include paths and native DPI library; Python can import this project |
| `02_stimulus`, `03_python` | Also the SvTypes SV runtime include path and generated model |

The top-level sources already include their dependencies. Do not separately
compile the included DUT, packages, or generated model a second time. The shared
run guide explains how to obtain the library locations and compile flags.

```sh
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
python -m examples.project_migration.generate
python -m examples.project_migration.generate --check
svx sv-files
svx compile-flags
svx libs
```

For source development, put `python` and `../svtypes/python` before additional
site-packages. The embedded Python needs those paths too; pytest's import-path
configuration does not configure the simulator process. This project uses typed
channels, not hierarchical signal access or an inheritance manifest.

Save the default runs as `run/00_sv.log` through `run/03_python.log`.

## 1. Establish A Pure SV Baseline

The original project starts five finite tasks:

```systemverilog
fork
  driver();
  monitor();
  legacy_sequence();
  legacy_responses();
  legacy_scoreboard();
join
check_complete();
report_complete();
```

Legacy records live in `common/legacy_types.svh`. Mailboxes connect the sequence,
driver, and checkers. Each checker owns its own reset-zero reference registers.
Do not combine the migration with a BFM rewrite or a sampling-edge change.

Required completion records:

```text
MIGRATION_SV_RESPONSES_PASS count=64
MIGRATION_SV_SCOREBOARD_PASS count=64
MIGRATION_PROJECT_PASS count=64 observations=64 waits=48
```

Verify every transaction and acceptance timestamp, not just the PASS string:

```sh
python -m examples.project_migration.verify run/00_sv.log --stage 00_sv
```

The first acceptance is at 35 ns, the last at 1775 ns, with 48 wait cycles.
`verify.py` needs only the standard library and can also run directly as a script
before SVX is installed.

## 2. Add Only The Python Entry

`01_entry/tb.sv` adds runtime setup and teardown around the original flow:

```diff
+ `include "sv/svx_pkg.sv"
+ import svx_pkg::*;
+ svx_init();
+ svx_run_test("examples.project_migration.scenarios", "entry");
  fork /* unchanged SV tasks */ join
  check_complete();
+ svx_shutdown();
  report_complete();
```

`entry()` is a synchronous function reporting `MIGRATION_PY_ENTRY_PASS`. It does
not create a Python clock, asyncio loop, or host thread. Failures at this step
are import/loading/lifecycle problems, not transaction-codec problems.

```sh
python -m examples.project_migration.verify run/01_entry.log --stage 01_entry \
  --baseline run/00_sv.log
```

All 64 data values, ordering, and timestamps must remain identical to pure SV.

## 3. Move Stimulus Through A Typed Boundary

`models.py` declares the sole cross-language schema with SvTypes. For example:

```python
@svobj(registry=package)
class MigrationRequest(SvObject):
    tag = Int()
    stop = Bit[1]()
    write = Bit[1]()
    address = Bit[8]()
    data = Bit[32]()
```

`generate.py` invokes public `svx svtypes-gen --channel-helpers`. The typed
checkpoints replace the legacy-type include with the generated model; do not
compile both definitions of the same class. Do not maintain a parallel byte
layout or expose response packing to scenario authors.

The adapters in `common/typed_boundary.svh` connect existing mailbox boundaries:

```systemverilog
svx_get_MigrationRequest("migration.bus.req", request);
requests.put(request);

responses.get(response);
svx_put_MigrationResponse("migration.bus.rsp", response);
```

The scheduling change is small:

```diff
- legacy_sequence();
- legacy_responses();
+ request_bridge();
+ response_bridge();
+ svx_run_test("examples.project_migration.scenarios", "stimulus");
  legacy_scoreboard();
```

Python uses `svx.reqrsp_channel("migration.bus", MigrationRequest, MigrationResponse)`
and `bus.request(request_for(op))`. The immutable Python `Operation` is a local
scenario plan, never the wire contract. Requests, responses, and observations
cross through SvTypes. The original monitor and SV scoreboard are still active.

```sh
python -m examples.project_migration.verify run/02_stimulus.log --stage 02_stimulus \
  --baseline run/00_sv.log
```

Require the Python response count and the original SV scoreboard count, as well
as complete trace equivalence.

## 4. Move The Independent Scoreboard

The final checkpoint replaces the remaining checking boundary:

```diff
- legacy_scoreboard();
- svx_run_test("examples.project_migration.scenarios", "stimulus");
+ monitor_bridge();
+ svx_run_test(python_module, python_test);
```

`monitor_bridge()` publishes the monitor's own `MigrationObservation` records.
The default Python `smoke` runs a producer and observer concurrently:

```python
svx.fork_join([producer, observer])
```

The producer checks responses. The observer checks every tag, operation,
address, value, and count. Expected results are computed into an immutable tuple
before either process starts, avoiding a race on a partially populated shared
dictionary. A correct driver response alone is not proof of correct pin activity.

```sh
python -m examples.project_migration.verify run/03_python.log --stage 03_python \
  --baseline run/00_sv.log
```

Require `MIGRATION_PY_SCOREBOARD_PASS count=64 addresses=4 operations=2`, the
response marker, and the project completion marker. The old SV sequence and
scoreboard are no longer started.

### Termination Is Part Of The Contract

Typed `stop=1` records terminate finite streams without a compiled transaction
count. The producer sends stop after its last request and consumes the response
acknowledgement. The driver finishes pin activity and sets `driver_done`; the
monitor exits and sends its own observation end record. The Python observer
consumes that record. Every Python process, SV adapter, and BFM joins before
`check_complete()`, shutdown, and the project PASS.

Neither the last response nor Python's return proves the monitor is finished.
Do not kill blocked processes to disguise incomplete normal shutdown. This
single-producer end protocol is not a general multi-producer drain protocol;
define aggregation explicitly when adopting it in a larger environment.

## Extend Python Without Recompiling

Run the same final binary with `+MIGRATION_TEST=stress`. It executes 4096 transfers,
exceeding the default channel capacity of 1024, and tests concurrent consumption
and termination rather than throughput:

```sh
python -m examples.project_migration.verify run/stress.log --stage 03_python \
  --count 4096 --salt 0x12345678
```

After compilation, create `runtime_added_migration_case.py` on the import path:

```python
import svx
from examples.project_migration.scenarios import program, run_program

@svx.test
def newly_added():
    run_program(program(192, salt=0xdeadbeef))
```

Start the unchanged binary with
`+MIGRATION_MODULE=runtime_added_migration_case +MIGRATION_TEST=newly_added`.
Do not regenerate the model, rebuild SV, or replace the native library.

```sh
python -m examples.project_migration.verify run/newly_added.log --stage 03_python \
  --count 192 --salt 0xdeadbeef
```

Run the original smoke again afterwards. Scenario/data/checker changes stay in
Python; changes to SvTypes fields or the SV protocol boundary require generation
and recompilation. This example has no inheritance discovery contract to check.

## Validate The Checkers Too

For each checkpoint, run with `+MIGRATION_CORRUPT_READ`: the DUT flips a read-data
bit and the first reset read must fail. Separately run pure SV and the final
checkpoint with `+MIGRATION_CORRUPT_OBSERVATION`. Only monitor record tag 8 is
damaged; driver responses remain correct, so the monitor checker must detect it.

```sh
python -m examples.project_migration.verify run/bad_monitor.log --stage 03_python \
  --expect-error MIGRATION_MONITOR_MISMATCH
```

Pure SV/entry read failures report `MIGRATION_SV_RESPONSE_MISMATCH` or
`MIGRATION_SV_MONITOR_MISMATCH`; the stimulus checkpoint reports Python response
mismatch or SV monitor mismatch; the final checkpoint reports Python response
or monitor mismatch. With concurrent checkers, which error appears first is not
specified. Repeat `--expect-error` to permit exactly those alternatives.

Require a matching checker diagnostic, a fatal, and no project PASS. Timeout,
crash, missing imports, or an arbitrary nonzero exit status are not successful
negative tests. Exit status alone may also be insufficient to identify a fatal.

## Practices To Carry Into A Real Project

- Preserve hardware/timing invariants and prove transaction/timestamp equivalence
  after each small change. Keep normal-path and injected-error acceptance separate.
- Separate requests, driver responses, and independent observations. Consume streams
  concurrently; do not conceal stalled consumers by increasing queue capacity.
- Keep one cross-language schema source and one generation entry. `--check` is
  read-only. Regenerate stale models; never repair generated code by hand.
- Specify sampling in protocol terms. A different DUT that updates responses in
  NBA needs an appropriate clocking/sampling contract, not copied `#0` delays.
- Join all finite work before completion. In an existing UVM project retain its
  phases, objections, and factory; Cookbook section 7.1 covers that entry route.

## End-To-End Qualification

Actual progress on 2026-10-24, not final acceptance:

| Gate | Result |
|---|---|
| Four default runs | Same 64-transfer data/order/timestamps as pure SV; 48 waits each |
| Final stress | Not qualified; the earlier run incurred heavy paging and was stopped; record lifetime handling remains pending |
| New module added after compilation | Not yet executed |
| Original smoke reused | Final rerun pending |
| DUT read corruption at all four stages | Specified checker failure and no project PASS |
| Independent monitor corruption, pure SV and final | Monitor checker detects both failures |
| Pre-conversion X/Z checks | Source added; new fault gates await remote validation |

Passing results above precede the additional X/Z guard. The current changes and
complete route still need qualification. Do not infer project-scale acceptance or
attribute memory pressure to an SVX core defect without independent investigation.
The larger adoption exercise will use an existing external project's SV environment;
this project remains introductory material only.
