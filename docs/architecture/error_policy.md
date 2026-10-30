# SVX Error Policy — Detailed Design

See [SVX_SPEC.md](../SVX_SPEC.md) Section 9.

## 1. Exception Taxonomy

All SVX-specific exceptions inherit from `svx.SVXError`.

```python
# python/svx/errors.py

class SVXError(RuntimeError):
    """Base class for all SVX-specific errors."""

class SVXContextError(SVXError):
    """Raised when an SVX primitive is called without a valid execution context."""

class SVXExportError(SVXError):
    """Raised when export registration or resolution fails."""

class SVXRemoteError(SVXInheritanceError):
    """Raised when a declared cross-language call fails."""

class SVXSignalError(SVXError):
    """Raised when hierarchical signal access fails."""
```

## 2. Policy Configuration

### 2.1 API

```python
import svx

# Set the exception policy globally.
svx.set_exception_policy(svx.FATAL)       # default
svx.set_exception_policy(svx.REPORT)

# Query current policy.
current = svx.get_exception_policy()
```

### 2.2 Policy Behaviors

| Policy | 1.0 support | Behavior |
|---|---|---|
| `svx.FATAL` | Yes (default) | Prints the exception and traceback, then terminates simulation via `$fatal`. |
| `svx.REPORT` | Yes | Reports entry/child exceptions without immediate `$fatal`; failed-child waits still fail. Generated inheritance and constructor failures remain fatal. |

### 2.3 Fatal Mechanism

The default `svx.FATAL` policy reports the error and then calls a simulator-side
SV function that executes `$fatal(2, message)`.

The path is an exported SystemVerilog function rather than
`vpi_control(vpiFinish, ...)`, so it is legal from a nonblocking callback:

```cpp
// C++ side
void svx_fatal(const char* source, const char* error_message) {
    std::fprintf(stderr, "SVX FATAL [%s]: %s\n", source, error_message);
    svx_fatal_svx(source, error_message);
}
```

```systemverilog
function automatic void svx_fatal_svx(string source, string message);
  $fatal(2, "SVX FATAL [%s]: %s", source, message);
endfunction
export "DPI-C" function svx_fatal_svx;
```

The severity level is fixed at 2. During an active DPI disable unwind, ordinary
exceptions still produce a traceback, but fatal dispatch is deferred to the next
safe `svx_start` or shutdown boundary. Cancellation is internal control flow,
not an ordinary failure. Do not swallow it; use `finally` for cleanup.

## 3. Exception Reporting Format

Cross-language method, constructor and field-access boundaries add an exception
note beginning with `SVX call path:`. It identifies the direction, receiver ID
and canonical method/class/field identity. Nested calls retain the deepest
available path in one note, for example:

```text
SVX call path: SV -> Python object=1 method_id=sv://p/Base#check -> Python -> SV object=1 method_id=sv://p/Base#check
```

This note supplements the original traceback; it does not replace the user's
exception, source location or cause. Native SV failures retain their existing
`SVXRemoteError` code and identity. Each boundary restores its diagnostic context
on success or failure, and cancellation is not annotated as an error. Constructor
continuations retain their copied diagnostic context along with the original
Python stack. This is not a new wire error protocol or general deadlock recovery.

When an uncaught exception escapes an SVX execution context, the report must include:

```
SVX FATAL [export source]:
  Exception type: <type>
  Message: <message>
  Traceback:
    File "<path>", line <n>, in <func>
      <source line>
    ...
```

Example:

```
SVX FATAL [svx_start('tests.basic_test.main')]:
  Exception type: ValueError
  Message: invalid delay value: -5
  Traceback:
    File "tests/basic_test.py", line 8, in main
      svx.delay(-5, "ns")
    File "python/svx/primitives.py", line 23, in delay
      raise ValueError("invalid delay value: -5")
```
