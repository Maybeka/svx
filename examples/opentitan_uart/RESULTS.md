# OpenTitan UART Migration Verification

[中文](RESULTS.zh-CN.md)

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
