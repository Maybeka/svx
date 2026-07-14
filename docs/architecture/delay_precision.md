# SVX Delay Precision & Timescale Handling

See [SVX_SPEC.md](../SVX_SPEC.md) Section 7.

## 1. API Surface

```python
svx.delay(value: int | float, unit: str = "ns") -> None
```

Supported units:

```text
"s", "ms", "us", "ns", "ps", "fs"
```

`value` may be an integer or floating-point duration. Negative values are
invalid. Zero is valid and maps to a zero-delay control.

## 2. Conversion Model

SVX preserves floating-point duration across the Python/C++ boundary.

Python validates the input and maps the unit string to an internal unit code.
It does not convert the duration to integer nanoseconds and does not apply
Python rounding.

The SystemVerilog side performs the actual unit conversion in `svx_pkg` by
using an explicit time literal for the requested unit:

```systemverilog
#(duration * 1ns)
#(duration * 1ps)
...
```

This lets the simulator apply normal SystemVerilog delay rounding to the
package's declared `timeprecision`.

## 3. Python-Side Validation

Conversion happens in `python/svx/primitives.py`, before the C extension call:

```python
import math

_UNIT_TO_CODE: dict[str, int] = {
    "s":  0,
    "ms": 1,
    "us": 2,
    "ns": 3,
    "ps": 4,
    "fs": 5,
}

def _to_delay_args(value: int | float, unit: str) -> tuple[float, int]:
    duration = float(value)
    if not math.isfinite(duration):
        raise ValueError(f"svx.delay() value must be finite, got {value!r}")
    if duration < 0:
        raise ValueError(f"svx.delay() value must be non-negative, got {value!r}")
    try:
        unit_code = _UNIT_TO_CODE[unit]
    except KeyError:
        raise ValueError(f"unsupported svx.delay() unit: {unit!r}") from None
    return duration, unit_code
```

The native call receives:

```python
duration, unit_code = _to_delay_args(value, unit)
_svx_native.delay(duration, unit_code)
```

## 4. DPI Boundary

The C++ wrapper passes a floating duration and unit code to SystemVerilog:

```cpp
void svx_delay_wrapper(double duration, int unit_code) {
    // validate SVX execution context, release GIL, then:
    delay_svx(duration, unit_code);
}
```

The SystemVerilog DPI task accepts the same pair:

```systemverilog
typedef enum int {
  SVX_TIME_S  = 0,
  SVX_TIME_MS = 1,
  SVX_TIME_US = 2,
  SVX_TIME_NS = 3,
  SVX_TIME_PS = 4,
  SVX_TIME_FS = 5
} e_svx_time_unit;

task automatic delay_svx(real duration, int unit_code);
  case (e_svx_time_unit'(unit_code))
    SVX_TIME_S : #(duration * 1s);
    SVX_TIME_MS: #(duration * 1ms);
    SVX_TIME_US: #(duration * 1us);
    SVX_TIME_NS: #(duration * 1ns);
    SVX_TIME_PS: #(duration * 1ps);
    SVX_TIME_FS: #(duration * 1fs);
    default: $fatal(2, "SVX invalid delay unit code: %0d", unit_code);
  endcase
endtask
export "DPI-C" task delay_svx;
```

## 5. Timeunit And Timeprecision

`delay_svx` must be compiled inside `svx_pkg`, and `svx_pkg` must declare
explicit time settings:

```systemverilog
package svx_pkg;
  timeunit 1ns;
  timeprecision 1ps;
  ...
endpackage
```

The package `timeprecision` is the effective rounding precision for SVX delay
M1. With `timeprecision 1ps`, all requested delays are rounded by the simulator
to the nearest picosecond according to SystemVerilog delay semantics.

The caller's local `` `timescale`` does not control SVX delay rounding, because
the delay expression is evaluated in `svx_pkg`.

## 6. Rounding Semantics

SVX intentionally delegates rounding to SystemVerilog.

Examples with `svx_pkg.timeprecision == 1ps`:

```python
svx.delay(1.5, "ns")     # SV sees #(1.5 * 1ns), effective delay 1500ps
svx.delay(0.5, "ps")     # SV rounds according to 1ps precision
svx.delay(0.4, "ps")     # may round to 0ps at 1ps precision
svx.delay(100, "fs")     # may round to 0ps at 1ps precision
svx.delay(1500, "fs")    # effective delay 2ps after SV rounding
```

SVX does not reject positive sub-precision delays. If the requested delay
rounds to zero in SystemVerilog, that is the same behavior a user would get
from an equivalent SV delay expression in the SVX package.

## 7. Internal Unit Conversion

SVX supports different user-facing time units by mapping each unit string to an
internal unit code and performing conversion in SystemVerilog.

This keeps the user API stable while allowing the internal package
`timeprecision` to change later. For example, a future implementation could
switch `svx_pkg` to:

```systemverilog
timeunit 1ps;
timeprecision 1fs;
```

without changing the Python API.

## 8. C++ Time Literal Integration

C++ time literals may provide compile-time convenience in a future runtime API:

```cpp
delay(10_ns);
delay(1_us);
```

These are independent of the Python `svx.delay` API. The Python API passes
floating duration plus unit code; the SV side performs conversion and rounding.

## 9. Testing

1. `svx.delay(10, "ns")` in a caller scope with `` `timescale 1ns/1ps`` —
   verify exactly 10ns elapsed.
2. `svx.delay(10, "ns")` in a caller scope with `` `timescale 1ps/1ps`` —
   verify exactly 10ns elapsed.
3. `svx.delay(1.5, "ns")` — verify 1500ps elapsed with `timeprecision 1ps`.
4. `svx.delay(1500, "fs")` — verify 2ps elapsed with `timeprecision 1ps`.
5. `svx.delay(100, "fs")` — verify the result matches the simulator's SV
   rounding for `#(100 * 1fs)` in `svx_pkg`.
6. `svx.delay(-5, "ns")` — verify `ValueError` is raised before crossing DPI.
