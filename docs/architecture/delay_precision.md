# Delay Conversion And Precision

This note owns time conversion and rounding. The public callable is
`svx.delay(value, unit="ns")`; application context and function/task restrictions
are specified in the [API Reference](../SVX_API_REFERENCE.md).

## Conversion Path

Python accepts an integer or floating duration with `s`, `ms`, `us`, `ns`, `ps`
or `fs`. It checks finite/nonnegative duration, valid units and the signed
64-bit simulator tick range. Zero is legal. Validation occurs before dispatch;
see `python/svx/primitives.py` for the current range calculation.

The native boundary preserves the floating duration and an internal unit code.
It does not truncate to integer nanoseconds or apply Python rounding. SV's
`delay_svx` selects an explicit time literal for that unit, for example
`#(duration * 1ns)` or `#(duration * 1ps)`. The simulator performs normal
SystemVerilog rounding at the package precision.

## Scope And Rounding

`delay_svx` is compiled in `svx_pkg`, currently with `timeunit 1ns` and
`timeprecision 1ps`. The caller's local timescale does not replace that scope.

| Request | Effective behavior at 1 ps precision |
|---|---|
| `svx.delay(1.5, "ns")` | 1500 ps |
| `svx.delay(0.4, "ps")` | Rounds to zero |
| `svx.delay(1500, "fs")` | 2 ps after SV rounding |
| `svx.delay(0, "ns")` | Zero-delay scheduling control |

Positive sub-precision durations are not rejected merely for rounding to zero.
Compare behavior with an equivalent SV delay expression in the same package,
not with a Python sleep or a differently scoped SV test.

## Native Boundary

The complete exported task also receives a process index and cancellation
state. Its declarations live in `sv/svx_timing.sv` and
`svx_runtime/include/svx/sv_dpi.hpp`; this note intentionally does not maintain
abbreviated C function pointer prototypes. The native wrapper checks context,
invokes the simulator-owned task and restores the caller's evaluator state on
return. See [State Isolation](gil_management.md) and
[ABI Checks](cross_layer_api.md) for those mechanisms.

Timing checks should cover fractional units, sub-precision rounding, caller
timescale independence, zero delay, invalid values and overflow. The runnable
[fork/join example](../../examples/milestone_1_fork/README.md) combines delays
with simulator-owned concurrency.
