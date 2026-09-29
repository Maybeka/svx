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
| `svx.REPORT` | Yes | Prints the same information, preserves a failure status for the caller, and does not invoke `$fatal`. |
| `svx.DEFER` | No | Not a public policy. |
| `svx.CALLBACK` | No | Not a public policy. |

### 2.3 Fatal Mechanism

The default `svx.FATAL` policy reports the error and then calls a simulator-side SV task that executes `$fatal(2, message)`.

The preferred path is an exported SystemVerilog task rather than `vpi_control(vpiFinish, ...)`, because `$fatal` carries simulator-native severity and failure semantics:

```cpp
// C++ side
void svx_fatal(const char* source, const char* error_message) {
    vpi_printf((PLI_BYTE8*)"SVX FATAL [%s]: %s\n", source, error_message);
    svx_fatal_svx(source, error_message);
}
```

```systemverilog
task automatic svx_fatal_svx(string source, string message);
  $fatal(2, "SVX FATAL [%s]: %s", source, message);
endtask
export "DPI-C" task svx_fatal_svx;
```

The severity level is fixed at 2 for the stable fatal policy.

## 3. Exception Reporting Format

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

## 4. Process-Level Error Handling (Post-M1)

When the `svx.DEFER` policy is implemented:

```python
group = svx.fork_join_none([child])
# ... some work ...
if group.status() == svx.FAILED:
    error_info = group.error()
    print(f"Child failed: {error_info.message}")
```

The process handle stores:
- Exception type
- Exception message
- Traceback string
- Timestamp of failure

## 5. Testing

1. Trigger an uncaught exception in a `main()` task → verify fatal output format.
2. Verify `SVXContextError` is raised when calling a primitive without context.
3. Verify `SVXExportError` is raised when `svx_start` references an unregistered name.
4. (Post-M1) Verify `svx.REPORT` policy does not terminate simulation.
