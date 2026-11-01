# OpenTitan UART Migration Verification

[中文](RESULTS.zh-CN.md)

## Original Qualification

Upstream revision: `724f378edf920eb5bc536a0d136158963c44186b`.
Qualification date: 2026-10-25.
The upstream working tree remains unchanged. Results distinguish unmodified
baseline qualification from SVX integration and independent Python checking.

| Gate | Cases | Acceptance |
| --- | --- | --- |
| Original upstream SV baseline | smoke, tx_rx, FIFO full/overflow/reset, parity error, loopback, interrupt; seed 1 | All 8 pass |
| Mixed ownership | Seeds 1/2/3 | 10 TX, 10 RX, 10 Python readbacks per run |
| Python ownership | Seeds 1/2/3 | 64 TX, 64 RX, 64 Python readbacks per run; original UART data scoreboard disabled |
| Python checker negatives | Captured TX corruption, loss and reordering | Each reports `UART_MODEL_STREAM TX` and terminates; no PASS marker |
| Retained SV test selection in the extended build | smoke, tx_rx, FIFO reset, parity error | Original SV paths still pass without starting Python |
| All-byte Python extension | Seeds 1/2/3 | 512 TX, 512 RX and 512 readbacks per run |
| New Python module after the build | `rotated_bytes_case`, seed 1 | 512 TX, 512 RX and 512 readbacks, without generation or compilation |

All 17 integration gates meet their acceptance criteria, including the three
deliberate checker-failure controls. The eight untouched baseline cases are
separate from those 17 gates.

Normal cases require `TEST PASSED CHECKS`, the appropriate
`UART_MIGRATION_PASS` marker, and UVM warning/error/fatal counts of zero. Negative
cases require the specific Python checker failure and SVX fatal path; a timeout,
crash or unrelated exception does not qualify. These UVM counts are not a claim
that the compiler emits no diagnostics.

Frozen-build checks cover the simulation binary, native SVX library, generated
SV/Python and artifact manifest: both contents and modification times must remain
unchanged between runs. The original baseline binary is retained separately.
The final audit reconciles all 17 logs against the same six frozen build files
and confirms the rotated-case module was added after the binary was built.

## Additional Original-Build Import Qualification

A separate output directory consumed the original build system's actual compiler
argv and working directory. The importer expanded 235 upstream source files
(including the original implicit UVM library), 27 include directories and nine
macros. Adding only this example's bridge yielded 236 source inputs and 517
actual source dependencies. No upstream sources, filelists or baseline outputs
were modified.

The newly generated sources were actually recompiled. Five seed-1 gates passed:
mixed mode, Python-led mode, all-byte Python extension, retained SV smoke, and
the specified TX-data corruption control. The all-byte gate again checked
512 TX, 512 RX and 512 readbacks. This is a separate build-input integration
qualification, not a replacement for the original 17-gate campaign or a broader
claim about upstream class discovery.

All five logs share the same six frozen build files by content and modification
time. Changing an imported command-line macro made `--check` reject the stale
configuration without modifying generated outputs; the original configuration's
read-only check passed. The untouched upstream checkout and original eight SV
baseline records were also audited separately.
The 16 build-import regression tests passed remotely. The updated complete local
Python suite passed all 1020 tests with no skips or expected failures.

## Additional Demand-Driven Library Qualification

Four actual compiler comparisons covered original directory order, reversed
directory order, reversed suffix order, and the first directory's later suffix
competing with the second directory's first suffix. SVX matched the original
tool's directory-first, suffix-second selection and recursively loaded the
selected unit's child dependency. An unrelated invalid library file was never
parsed. Separate probes confirmed exact-basename search without a suffix list
and shared-compilation-unit macro visibility in selected library sources.

The original UART build then gained this library search context and an
independent library-selection check top. The same class boundary was exported,
generated and actually recompiled. Four seed-1 gates passed: mixed mode,
Python-led mode, all-byte Python extension, and retained SV smoke. Every run
also checked native library selection; the all-byte case retained its
512 TX, 512 RX and 512 readback checks.

All four logs share six frozen build files. Generated Python/SV class text is
byte-identical to the previous export. Editing an unused library file left
read-only checks passing; adding a new earlier candidate without changing the
command or filelist made the check reject stale output without modifying it.

These gates qualify demand-driven source parsing and class export, not automatic
generation of additional library declarations or all proprietary library/config
binding syntax.
The 23 library/config regression cases passed remotely; the complete local Python
suite passed 1027 tests with no skips or expected failures.

## Package-Only Analysis Qualification

On 2026-10-30 the direct export was rerun with --sv-elaboration packages against
the complete original input context:236 explicit sources,517 physical SV
dependencies,27 include directories and9 macros. The20 selected methods and11
ancestors were preserved; generation and read-only checks passed. Frozen-binary
seed1 runs passed mixed, Python-led and retained-SV modes. No upstream source or
simulation input was removed.

For a one-method manifest workload on the same current source revision,
Python3.13.7/pyslang11.0.0, three fresh processes per mode and unflushed OS caches
measured median2.723s/~241MiB peak RSS for all and1.809s/~187MiB for packages.
Both made9 parser requests but only3 raw parse batches. These sequential host
measurements are not whole-SoC compilation or simulation timings, nor proof of
persistent incrementality. All517 physical dependencies remained in this UART
input; the result is not explained by deleting explicit RTL files.

An independent library-loading control used12 RTL library files with18000 signal
declarations, selected through -y, and three alternating fresh-process samples
per mode. Manifest medians were7.259s versus0.145s, with13 versus1 selected source
dependencies and identical exported contracts. In contrast, a single explicitly
listed source containing12000 generated lanes showed no meaningful speedup from
top selection alone. The distinction matters: library-graph pruning saves loading
work; lazy elaboration and explicit RTL parsing are separate costs.

## Integrated Source-Copy Qualification

On 2026-10-31 the same20-method/11-ancestor direct export used --integrated and
--sv-elaboration packages. All236 original explicit inputs were consumed in
their shared-unit order. The generated source.sv copied active includes and
original packages/classes in place, then emitted the ordinary records and
bridges after their native type declarations. The integrated source replaced
the original SV input list for a fresh actual compilation; both were not
compiled together. Original tool options and native UVM support were retained.

The new binary passed seed1 mixed, Python-led and retained-SV modes. Each run
checked all generated SV/Python files from the artifact inventory, plus the
binary, native library and artifact manifest, by content and modification time.
The original upstream checkout and earlier separate-layout builds were not
modified. This qualifies the integrated UART class/handle boundary; nested
enum/struct and package callable/VIF integration is separately checked by the
direct-export examples. It does not qualify unfinished non-package instance
bindings or alternating-lineage automatic-record placement.

On 2026-11-01 the same original inputs were exported again after original-tree
reuse was added to source-copy generation. The complete source copy and bridges
were rebuilt with original compiler options, implicit libraries and DPI linkage;
seed1 mixed, Python-owned and retained-SV modes pass with zero runtime UVM
warnings/errors/fatals. These are separate from the original baseline counts.

Three paired export+check comparisons with raw syntax reuse enabled/disabled
produce byte-identical SV/Python, artifact and provenance files. Extra original
buffer parsing in the source-copy stage drops from2batches per pair to0, but
elapsed workflow time does not show a stable improvement. Initial parsing and
expanded/generated-text parsing remain.

A subsequent three-pair comparison kept the same syntax reuse in both modes
and changed only build-input bookkeeping: ordered source lists now use
set-based duplicate checks, and absent source exclusions do not trigger another
path-matching pass. Median full export+check time was19.586s before and19.061s
after (~2.7% lower); all three pairs produced identical outputs. These serial
fresh-process measurements use warm OS caches and time the CLI calls, excluding
interpreter/import startup and native compilation. Filelists, environment
expansion, source existence and dependency contents are still revalidated;
this is not persistent configuration caching or changed-unit parsing.

## Incremental Export Qualification

On 2026-10-31 the complete20-method/11-ancestor direct export used --incremental
with packages-mode analysis and the original236 explicit sources/517 physical
dependencies/~4.8MB input context. Python3.13.7/pyslang11.0.0 ran three alternating
fresh-process pairs, without flushing OS caches. A forced full export (discovery,
generation, input validation, explicit startup generation and cache certification)
had median13.828s including process startup. The following warm --check had
median0.987s. Every warm worker
forbade the SV parser and observed zero raw parse batches; every cold refresh
observed18. This is a whole-export20-method workload, not the earlier one-method
manifest-only measurement or simulation runtime.

Warm checks left generated files and the cache unchanged by content and
modification time. All20 incremental regression cases passed in the remote
Python environment, alongside the previously qualified library/frontend tests.
Generated SV/Python files were then
compared byte-for-byte with the qualified direct-export build; all matched.
Reusing that unchanged binary/library and its required runtime database, seed1
mixed, Python-led and retained-SV modes passed frozen-output checks.

This qualifies whole-export no-op reuse and its invalidation rules, not
per-unit AST caching or changed-unit-only parsing. A changed dependency currently
selects the full frontend. Cache data remains local and is not a published
manifest/runtime contract.

## Declaration Inventory Qualification

On 2026-10-31, inspect reused the original UART compiler configuration plus the
bridge source in packages analysis mode. Three fresh processes, without flushing
OS caches, each reported517 physical dependencies,3268 declarations and488 class
declarations using one raw parse batch and no instance elaboration. The complete
JSON inventory was identical across runs. Median wall time including process
startup was1.678s. This measures read-only declaration listing, not semantic
signature qualification or export generation; owner-bridge-pending entries are
not evidence that their scopes can already be exported. The related inventory,
library-search and source-sharing regressions passed26 cases remotely.

## Compilation-Unit Integration Follow-Up

On 2026-10-31 the full original shared-unit UART configuration was regenerated,
checked and compiled again with the explicit svx_exports_pkg::initialize startup
entry. The20-method/11-ancestor export passed frozen mixed, Python-led and
retained-SV seed1 execution with the existing native library. Separate native
qualification of the direct-export independent-unit example preserves macro
widths5/13 and two same-named unit classes returning11/22, plus Python-owned
construction, field access,2ns output/inout task timing and SV-handle virtual
callbacks. That example qualifies independent output boundaries; the original
UART input remains shared and was not silently changed to independent units.

## Integration Findings

- SV virtual callbacks from concurrent processes must not share one host-thread
  recursion stack or Python evaluator state. The independent
  `callback_interleaving` regression checks overlapping calls on the same object,
  non-LIFO returns, nested function callbacks and causal context preservation.
- The core fix is also checked against DPI signatures, actual cycle rejection,
  object/static/nested-callback cancellation and both SV-root/Python-root
  construction chains. The final Python suite reports 994 passing tests, with
  no skips or expected failures; the local native source build also succeeds.
- Turning off the original scoreboard removes more than comparisons: upstream
  idle helpers consult RAL mirror state maintained by that scoreboard. The
  integration adapter therefore polls real CSR responses directly. A larger
  all-byte case caught FIFO loss that the short case did not reveal. The checker
  was not weakened to accommodate it.

## Direct Source Export

The original full UART compile inputs also qualified `svx export` selecting
UartSequence and 20 method names, without declaration JSON or a decorated Python
target. Discovery retained 11 ancestors and evaluated native class type
parameters, generated/checked the artifacts and compiled the full environment.
Using those artifacts, mixed mode, Python-owned scenario/checking mode and the
original SV test all passed at seed 1. Deliberate TX data corruption was caught
by the Python checker. The run gates confirmed that compiled/generated artifacts
remained byte- and timestamp-identical during each run.

This qualification found and fixed a frontend defect: native class type arguments
must retain their concrete SV type, not the RemoteRef transport carrier or an
uninstantiated template parameter alias. It does not qualify whole-UVM export.

## Scope

This is an end-to-end migration of byte-transaction scenarios and independent
stream/frame/readback checks. It is not a port of every upstream CSR prediction,
interrupt, FIFO overflow, timeout, reset-recovery and coverage algorithm into
Python. The original baseline exercises those original SV paths; it must not be
counted as Python-model coverage. Source discovery of the whole upstream class
tree and automatic extraction of every UVM declaration are also not claimed.

The three main seeds exercise parity-disabled and odd-parity configurations;
mixed-mode seed 3 additionally exercises even parity. All-byte cases cover every
byte value, including the signed-byte boundary used by the native method API.
