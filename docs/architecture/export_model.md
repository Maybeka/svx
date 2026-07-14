# SVX Python Export Model — Detailed Design

See [SVX_SPEC.md](../SVX_SPEC.md) Section 6.

## 1. Design Principle

Python functions callable from SystemVerilog must be **explicitly exported**. Arbitrary dynamic function lookup without explicit export is not supported.

This is a security and debuggability decision:
- Export names are deterministic and discoverable.
- Registration failures are caught at module load time, not at the first DPI call.
- The registry can be inspected for debugging (`svx.list_exports()`).

## 2. API

### 2.1 Export Decorator

```python
# python/svx/export.py

import svx._registry as _reg

def export(func: Callable = None, *, name: str = None) -> Callable:
    """Register a Python function for SystemVerilog invocation.

    Args:
        func: The function to export. If called as @svx.export without
              arguments, func is passed as the first positional argument.
        name: Optional override for the export name. If not provided,
              defaults to '<module>.<func.__name__>'.
    """
    def decorator(f):
        export_name = name or _reg.default_name(f)
        _reg.register(export_name, f)
        return f

    if func is None:
        return decorator
    return decorator(func)
```

### 2.2 Usage

```python
# tests/basic_test.py
import svx

@svx.export
def main():
    svx.display("hello")

@svx.export(name="custom.name")
def alternate_entry():
    svx.display("alternate")
```

Registers:
- `tests.basic_test.main` → `main`
- `custom.name` → `alternate_entry`

### 2.3 Name Resolution

The default export name is constructed from the function's module and qualified name:

```python
# In _registry.py
import inspect

def default_name(func: Callable) -> str:
    module = func.__module__           # e.g., "tests.basic_test"
    qualname = func.__qualname__       # e.g., "main"
    return f"{module}.{qualname}"      # "tests.basic_test.main"
```

## 3. Registration Lifecycle

### 3.1 When Registration Happens

Registration occurs when the `@svx.export` decorator runs, i.e., when the Python module is loaded via `svx_load`.

```
svx_load("tests.basic_test")
    → PyImport_Import("tests.basic_test")
        → Python executes tests/basic_test.py top-level
            → @svx.export on main() runs
                → _registry.register("tests.basic_test.main", main)
```

### 3.2 When Registration Fails

- **Duplicate name**: If two functions register the same export name, `SVXExportError` is raised at module load time.
- **Name collision across modules**: The registry is global, so two modules cannot export the same name. If needed, use the `name=` override to disambiguate.
- **Empty module**: Loading a module with no exports is valid (no-op). Future SVX features may use modules for configuration or type definitions without exports.

### 3.3 Duplicate Protection

```python
_registry: dict[str, Callable] = {}

def register(name: str, func: Callable) -> None:
    if name in _registry:
        existing = _registry[name]
        raise SVXExportError(
            f"Export name '{name}' is already registered by "
            f"'{existing.__module__}.{existing.__qualname__}'. "
            f"Cannot re-register from '{func.__module__}.{func.__qualname__}'."
        )
    _registry[name] = func
```

## 4. SystemVerilog Entry Points

### 4.1 svx_load

```systemverilog
task svx_load(string module_name);
```

- Calls `PyImport_Import(module_name)` from the C++ runtime.
- If the module cannot be imported (ImportError), raises `SVXExportError` on the SV side (via `$fatal` or return status).
- Side effect: `@svx.export` decorators in the module execute, populating the registry.

### 4.2 svx_start

```systemverilog
task svx_start(string export_name);
```

- Resolves `export_name` in the registry.
- If not found, raises `SVXExportError`.
- If found, creates an SVX execution context and invokes the callable.
- Blocks until the callable returns (from the SV process perspective).

### 4.3 Ordering Contract

`svx_load` must precede `svx_start` for the target module:

```systemverilog
// Correct
svx_init();
svx_load("tests.basic_test");   // registers exports
svx_start("tests.basic_test.main");  // resolves and runs

// Incorrect — will raise SVXExportError
svx_init();
svx_start("tests.basic_test.main");  // not yet registered
svx_load("tests.basic_test");        // too late
```

## 5. Debugging Support

```python
# Inspect the registry
>>> import svx
>>> svx.list_exports()
{
    'tests.basic_test.main': <function main at 0x...>,
    'tests.basic_test.background': <function background at 0x...>,
}
```

This is implemented as `list(_registry.items())` and is available when running Python outside the simulator (no context required).

## 6. Exported Function Signature

Exported functions must accept zero arguments (for M1). Any required configuration should be captured via module-level state, configuration objects, or (post-M1) function parameters with type marshalling:

```python
# M1: no arguments
@svx.export
def main():
    ...

# Post-M1 (planned): keyword arguments with SvTypes marshalling
@svx.export
def main(*, addr: Bits(32), data: Bits(64)):
    ...
```

## 7. Testing

1. Define a module with two exports, call `svx.list_exports()` → verify both appear.
2. Define two functions with the same export name → verify `SVXExportError`.
3. `svx_start` with an unregistered name → verify `SVXExportError`.
4. `svx_start` without prior `svx_load` → verify `SVXExportError`.
5. Module with no exports → `svx_load` succeeds, `svx.list_exports()` shows nothing.
