# Migrating OpenTitan UART Verification to SVX

[中文](README.zh-CN.md)

Shared setup and runtime-loading details: [example run guide](../RUNNING_EXAMPLES.md).

This project starts with the real OpenTitan UART verification environment, not a
replacement UART driver. It demonstrates two ownership choices over the same
RTL, interfaces, agents, register model and virtual sequencer:

| Layer | Mixed mode | Python-led mode |
| --- | --- | --- |
| UART/TL pin timing, drivers and monitors | Original SV | Original SV |
| UART initialization and register services | Original SV | Original SV |
| Scenario scheduling | Original SV sequence body | Python `body()` |
| TX transaction generation | Original SV `process_tx()` | Python `process_tx()` |
| RX transaction generation and readback checks | Python | Python |
| Byte-stream model and frame checks | Python, alongside original SV checker | Python, original UART data checker disabled |
| Protocol and security assertions | Retained | Retained |

The Python-led example owns its test algorithm and expectations. It does **not**
claim to replace the upstream UART scoreboard's entire CSR, interrupt, timeout,
error-injection and coverage model. Existing SV tests remain valuable and runnable.

## 1. Establish the Unmodified Project

Use OpenTitan commit `724f378edf920eb5bc536a0d136158963c44186b` and its documented
dependencies. The original configuration is `hw/ip/uart/dv/uart_sim_cfg.hjson`.
Keep that checkout separate from SVX and follow OpenTitan's installation guide.
The [pinned UART DV sources](https://github.com/lowRISC/opentitan/tree/724f378edf920eb5bc536a0d136158963c44186b/hw/ip/uart/dv)
contain the environment and sequences; native driver/monitor/item definitions
are under upstream `hw/dv/sv/uart_agent`.

First run the unmodified environment through its own DVSim entry point:

```sh
dvsim hw/ip/uart/dv/uart_sim_cfg.hjson \
  -i uart_smoke uart_tx_rx uart_fifo_full uart_fifo_overflow \
     uart_fifo_reset uart_rx_parity_err uart_loopback uart_intr \
  --fixed-seed 1 --max-parallel 1
```

Do not disable assertions or the scoreboard to make this baseline pass. Record
the source revision, original build command, binary identity, case names, seeds
and UVM severity summaries. These become the reference for subsequent changes.

## 2. Select a Small, Real Class Boundary

[`uart_bridge.sv`](uart_bridge.sv) adds `UartSequence extends uart_smoke_vseq`.
It inherits the actual upstream initialization, constraints, sequencer behavior
and transaction services. Its extra methods expose a register read result and
owned monitor observations; they do not implement a second UART agent.

Export the original compiler invocation from the existing build:
`compiler-input.json` contains exactly `directory` and `arguments`, with the
compiler executable as argv[0]. Reuse it rather than listing UVM, UART and RTL
dependencies, definitions and include paths again:

```sh
svx compile-config --sv-build-command "$UART_BUILD_COMMAND"
svx export --class uart_svx_bridge_pkg::UartSequence \
  --member body process_tx process_rx uart_init dut_shutdown \
    spinwait_txidle spinwait_rxidle send_tx_byte send_rx_byte read_rx \
    observed_count observed_item parity_enabled parity_odd \
    item_data item_frame item_identity same_item make_item set_item_data \
  --sv-build-command "$UART_BUILD_COMMAND" \
  --sv-source examples/opentitan_uart/uart_bridge.sv --out "$UART_GENERATED"
```

The CLI discovers the 20 selected signatures and complete 11-ancestor lineage
from source, including evaluated native class type parameters. There is no
declarations JSON or artificial Python target. Only UartSequence is an export
target; imports and native class handles do not request exporting all of UVM.
Repeat the same export command with `--check` for a read-only gate. Retain the original compiler
environment to locate implicit UVM sources. See [build input import](../../docs/SVX_BUILD_INPUTS.md)
for the format and support limits. Resolving this selected boundary's dependency
context does not select the entire upstream class tree for generation.

[`generate.py`](generate.py) retains an explicitly maintained contract snapshot
for inspecting the example without upstream sources. It uses the same backend,
but is not required by direct source export. Do not mix snapshot and discovered
outputs in one generated directory.

Original `-y` / `+libext+` options remain ordered search context: SVX selects
specific files for missing design units instead of expanding the directory.
Unused files do not enter parsing or dependency records. Keep the same command
for read-only checks. Additional qualification compared actual compiler library
selection and reran both UART migration modes in a full build with source-library
lookup; see [results](RESULTS.md).

Add [`tb_migration.sv`](tb_migration.sv) after the original UART environment packages in the existing
build's compilation list. Add the SVX repository root, SvTypes runtime directory
and `$UART_GENERATED` to the include search path; add
`uart_svx_migration_registration` as a top-level module alongside the original
top-level modules. The source includes the bridge before generated `mirrors.sv`.
Build/load the matching native SVX runtime as described in the
[integration guide](../../docs/SVX_USER_MANUAL.md).
For the direct source-export command above, call the reported
`svx_exports_pkg::initialize()` after `svx_init()` and before `svx_load()` in that
top to explicitly register generated factories and dispatchers.

Alternatively add `--integrated` to the same export command. Replace original
inputs using `source_replacements` and `systemverilog_compile_order` from
artifacts.json, with the SvTypes/SVX runtime packages compiled first. Do not also
compile the original list or a separate bridge/mirrors file. Remove the four
leading duplicate includes from the migration top, retaining its test package
and registration module, and use the same initialize call. Preserve original
implicit library options and DPI linkage even when library source text appears
in the expanded copy. This mode has been rebuilt and verified in mixed, Python
and retained-SV modes; see [results](RESULTS.md).

Preserve the original build's access, assertion, language and instrumentation
options. Extend that build rather than reconstructing its RTL file list by hand.
Only the new build's outputs should change; keep the original baseline binary.

The generated public Python name is
`svx_mirror.uart_svx_bridge_pkg.UartSequence`. Keep the generated Python directory
and this example directory on `PYTHONPATH`; set `SVX_ARTIFACT_MANIFEST` to the
generated `artifacts.json`.

## 3. Export Real Transactions, Not Detached Dictionaries

`UartCapture` independently subscribes to the original UART monitor's TX/RX
analysis ports. It does not consume the original scoreboard's FIFO. Each callback
clones the native `uart_item`, since a producer may reuse or mutate its item.

`observed_item(tx, index)` returns a typed
`RemoteRef["sv://uart_agent_pkg/uart_item"]` to that owned native snapshot.
The class is intentionally opaque in this example: `item_data`, `item_frame` and
`item_identity` are generated, typed calls on `UartSequence` that accept the handle.
This is not a promise of automatic arbitrary member access on an opaque handle.

```python
item = sequence.observed_item(1, index)
assert sequence.same_item(item, sequence.observed_item(1, index))
data = sequence.item_data(item)
```

The creation gate also calls `make_item()`, changes the actual SV object's data
through `set_item_data()` and verifies that its native identity remains unchanged.
Snapshot ownership and live-handle identity are different concerns: cloning
stabilizes monitor observations; repeated export of the same snapshot keeps its
identity. Handles are session-scoped and must not be reused after shutdown.

## 4. Migrate One Side First

Select `+UVM_TESTNAME=UartMigrationTest`, `+en_scb=1`, and set
`UART_MIGRATION_MODE=mixed` in the simulation process environment.

The single SV test adapter handles UVM configuration and sequencer handoff.
Python creates `PythonUart`, publishes it, and SV obtains the native base handle
with `SVX_GET_OBJECT`. No transaction payload protocol is exposed to user methods.

The native UVM lifecycle still matters:

```systemverilog
configure_sequence(sequence_handle);
if (!sequence_handle.randomize()) `uvm_fatal("UART_RANDOMIZE", "native constraints failed")
sequence_handle.start(env.virtual_sequencer);
```

Construction alone does not attach the sequencer/configuration. Keep Python
`__init__` for local model setup; do not start configuration-dependent bus activity
there before the normal UVM handoff.

```python
def body(self):
    if self.mode == "mixed":
        super().body()
```

The original body still forks TX/RX and performs its two rounds. TX generation
remains in SV; Python replaces RX generation/readback. Both directions pass
through `send_*_byte` virtual hooks, so Python records the intended bytes before
calling the original SV implementation. The original checker and Python checker
run together at this stage.

The host keeps its UVM objection until Python checks finish, then closes the
pair and shuts SVX down before dropping the objection. Cleanup is not placed
after the original `run_test()`, which may end simulation without returning.

## 5. Move the Scenario and Checker Ownership

Use the **same binary and generated contracts**, change
`UART_MIGRATION_MODE=python`, and select `+en_scb=0`.

```python
for _ in range(2):
    self.uart_init()
    svx.fork_join([self.process_tx, self.process_rx])
    self.dut_shutdown()
```

Python chooses and sends 64 TX and 64 RX bytes in total, including zero, all ones
and alternating-bit patterns. It checks 64 register readbacks. Native methods
still perform CSR access, UART bit timing and idle waiting; the Python code never
drives pins or uses an asynchronous event loop. The one-microsecond wait after a
TX write is an explicit settling delay for this scenario, not a generic sampling
barrier or a substitute for native protocol synchronization.

Do not assume a helper becomes independent when its scoreboard is disabled.
The upstream idle helper first reads `ctrl.get_mirrored_value()`, whose predictor
belongs to that scoreboard. `UartSequence` therefore overrides the idle services
to poll actual CSR read responses, with a timeout. Without this change, the short
case can fit in a FIFO while a larger case silently overflows; the Python checker
must report the resulting lost observations, not accept a shorter stream.

[`model.py`](model.py) owns separate TX/RX expectations and compares **independent
monitor observations** for values, count, order, start/stop bits and enabled parity.
It does not read the original scoreboard's private queues or prediction fields.
RX register data is additionally checked against Python intent. This example
performs final stream comparison; it is not a lossless unbounded streaming logger.

The SV adapter is one reusable host for both modes, not one generated SV test per
Python scenario. This example uses the existing SV test name as its host; it does
not introduce a second Python UVM factory. Runtime Python test-name registration
is covered separately by the UVMX chapter in the [Cookbook](../../docs/SVX_COOKBOOK.zh-CN.md).
Its source-only example is `incubator/uvmx/examples/peer_test_selection` in the
repository, outside the packaged core examples.

## 6. Prove the Checker Can Fail

The observation tap supports three explicit negative controls:

| Option | Injected observation fault | Expected Python diagnostic |
| --- | --- | --- |
| `+UART_SVX_CORRUPT_TX` | Corrupt captured TX data | `UART_MODEL_STREAM TX` |
| `+UART_SVX_DROP_TX` | Drop the first captured TX item | `UART_MODEL_STREAM TX` |
| `+UART_SVX_REORDER_TX` | Swap the first two captured TX items | `UART_MODEL_STREAM TX` |

Run these in Python-led mode with `+en_scb=0`: they must terminate through the
normal SVX fatal policy and must never print `UART_MIGRATION_PASS` or
`TEST PASSED CHECKS`. The injected fault is after the monitor, not in DUT RTL;
its purpose is to prove the independent Python checker is active.

Also rerun original SV cases using `+UVM_TESTNAME=uart_base_test`, the original
`+UVM_TEST_SEQ`, and `+en_scb=1`. That selection does not initialize Python.

## 7. Add a Python Case Without Rebuilding

[`all_bytes_case.py`](all_bytes_case.py) derives `Test(PythonUart)` and supplies
all 256 byte values per round, in opposite TX/RX orders. This checks 512 TX,
512 RX and 512 readbacks over two rounds. [`rotated_bytes_case.py`](rotated_bytes_case.py)
is a separate extension module with two different permutations of all byte values.

```python
from uart_migration import PythonUart

class Test(PythonUart):
    def tx_pattern(self):
        return tuple((index * 73 + 19) & 255 for index in range(256))
```

Set `UART_MIGRATION_CASE_MODULE=rotated_bytes_case` together with
`UART_MIGRATION_MODE=python`, and retain the same UVM host and `+en_scb=0`.
The entry point imports the requested module's `Test` and constructs the actual
Python subclass through the same SVX mirror. No new SV class, virtual slot,
manifest target or generated bridge is introduced. After building, the new module
can be added using only Python source changes. This case selector belongs to this
project; it is not registration of a new `+UVM_TESTNAME`.

Check the existing generated contract without rewriting it by repeating the
section 2 export command with `--check` and the same original build inputs.

## Verification And Iteration

The acceptance record is summarized in [RESULTS.md](RESULTS.md). Separate failures
in the original project, generation, native/class bridging and Python model:
retain the full UVM report and original exception, not just the process exit code.

After the first build, changing a Python method body or model requires only a new
simulation process. Changing a selected signature, SV helper, class contract or
generated code requires regeneration/recompilation. Verify reuse with binary,
native-library and generated-file hashes rather than inferring it from a fast run.

OpenTitan remains an external Apache-2.0 project. This directory contains the SVX
integration, not a vendored copy of its RTL/DV tree. Preserve the upstream license
and notices when distributing derived source or patches.
