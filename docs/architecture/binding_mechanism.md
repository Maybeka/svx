# SVX Python↔C++ Binding Mechanism

See [SVX_PROJECT_LAYOUT.md](../SVX_PROJECT_LAYOUT.md) Section 3 and Section 7.

## 1. Binding Technology

SVX uses the **CPython C API directly** (`<Python.h>`) for the Python↔C++ binding. No third-party binding framework (pybind11, nanobind, ctypes, cffi) is required.

### Rationale

- The SVX runtime already links against CPython for interpreter embedding. Using the C API adds no new dependency.
- The binding surface is small for M1: ~6 primitives (`display`, `delay`, `fork_join`, `fork_join_any`, `fork_join_none`, `set_exception_policy`).
- The primitives are thin wrappers that delegate to existing C++ functions. A full binding framework adds complexity without benefit for this surface area.

`pybind11` or `nanobind` may be adopted in a future milestone if the binding surface grows significantly (e.g., VPI signal access, type marshalling).

## 2. Shared Library Architecture

```
svx_runtime/
├── CMakeLists.txt
├── include/svx/
│   ├── svx.hpp              # Public C++ API
│   ├── context.hpp          # ExecutionContext
│   └── ...
├── src/
│   ├── svx.cpp              # Main entry point
│   ├── context.cpp
│   ├── process.cpp
│   ├── fork.cpp
│   ├── timing.cpp
│   ├── display.cpp
│   ├── vpi.cpp
│   └── python_bindings.cpp  # CPython C extension module
```

A single shared library binary serves dual purpose:

1. **Loaded by the simulator** via `-sv_lib libsvx.so` (or equivalent simulator flag).
2. **Imported by Python** as a C extension module (`import _svx_native`).

The build must expose that same binary under both loader-facing names:

- simulator-facing name: `libsvx.so` / `libsvx.dylib` / `svx.dll`
- Python-facing extension name: `_svx_native.<python-extension-suffix>`

For development, the Python-facing file should be a symlink, hardlink, or platform-specific alias to the simulator-facing library. A plain file copy is not acceptable unless the platform loader is proven to de-duplicate it, because a copied shared object may create a second SVX runtime instance with separate global state.

The important requirement is that both names resolve to one SVX runtime instance and shared process state.

### 2.1 Simulator Loading

The simulator loads `libsvx.so` for DPI function resolution. The library must export:

- DPI functions called by SystemVerilog: `svx_process__exec`, `svx_process__set_svobj_idx`.
- Runtime entry points used by the SV package, such as `svx_runtime_init`, `svx_runtime_load`, and `svx_runtime_start`.

### 2.2 Python Import

Python `import _svx_native` loads the Python-facing extension file. The library registers a CPython module on load:

```cpp
// In python_bindings.cpp
static PyMethodDef SVXMethods[] = {
    {"delay", svx_native_delay, METH_VARARGS, "Advance simulation time"},
    {"display", svx_native_display, METH_VARARGS, "Print message via simulator"},
    {"fork_join", svx_native_fork_join, METH_VARARGS, "Fork-join callables"},
    {"fork_join_any", svx_native_fork_join_any, METH_VARARGS, "Fork-join-any callables"},
    {"fork_join_none", svx_native_fork_join_none, METH_VARARGS, "Fork-join-none callables"},
    {"set_exception_policy", svx_native_set_exception_policy, METH_VARARGS, "Set error policy"},
    {"get_exception_policy", svx_native_get_exception_policy, METH_NOARGS, "Get current error policy"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef svxmodule = {
    PyModuleDef_HEAD_INIT,
    "_svx_native",
    "SVX native runtime bindings",
    -1,
    SVXMethods
};

PyMODINIT_FUNC PyInit__svx_native(void) {
    return PyModule_Create(&svxmodule);
}
```

## 3. Python Package Structure

```
python/svx/
├── __init__.py       # Public API: re-exports from internal modules
├── _native.py        # Thin wrapper: import _svx_native, add validation
├── export.py         # @svx.export decorator
├── _registry.py      # Internal export registry
├── context.py        # SVXContextError + context validation helpers
├── primitives.py     # User-facing: display, delay, fork_join, etc.
├── process.py        # ProcessGroup class
└── errors.py         # Exception classes, policy configuration
```

### 3.1 Import Chain

```
User code:     import svx
                    │
                    ▼
python/svx/__init__.py  ─── imports ──→  primitives.py, export.py, errors.py
                    │                            │
                    │                            ▼
                    │                     _native.py
                    │                            │
                    │                            ▼
                    │                     import _svx_native  (C extension .so)
                    │
                    ▼
            User calls svx.delay(10, "ns")
                    │
                    ▼
            primitives.py validates context
                    │
                    ▼
            _native.py calls _svx_native.delay()
```

### 3.2 Validation Layer

User-facing primitives validate user arguments before calling the C extension. They may also perform a convenience context check through `_svx_native`, but the C extension remains the source of truth and must reject primitive calls without a native SVX execution context.

```python
# python/svx/primitives.py
from svx._native import _svx_native
from svx.context import validate_delay_value, validate_delay_unit

def delay(value: int, unit: str = "ns") -> None:
    validate_delay_value(value)
    validate_delay_unit(unit)
    # Preserve floating duration and map unit to an internal code.
    duration, unit_code = _to_delay_args(value, unit)
    # _svx_native.delay performs the required native context check.
    _svx_native.delay(duration, unit_code)
```

## 4. Build Integration

### 4.1 CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.15)
project(svx_runtime LANGUAGES CXX)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

add_library(svx SHARED
    src/svx.cpp
    src/context.cpp
    src/python_runtime.cpp
    src/export_registry.cpp
    src/process.cpp
    src/fork.cpp
    src/timing.cpp
    src/display.cpp
    src/vpi.cpp
    src/python_bindings.cpp
)

target_include_directories(svx PRIVATE
    include
    ${Python3_INCLUDE_DIRS}
)

target_link_libraries(svx PRIVATE
    ${Python3_LIBRARIES}
)
```

### 4.2 pyproject.toml

The Python package declares no build dependency on the C extension — it imports `_svx_native` at runtime. The extension is expected to be on `sys.path` via:

- Simulator environment (when running inside a simulator).
- `PYTHONPATH` or a `.pth` file pointing to the build output.
- Installation alongside the Python package files.

For development workflows, the `tools/build_svx.py` script builds the C++ library and places it where Python can find it.

## 5. Alternative Considered: Separate Extension Module

An alternative is building two separate shared libraries:

1. `libsvx_runtime.so` — loaded by the simulator (DPI functions only).
2. `_svx_native.cpython-*.so` — loaded by Python (CPython extension).

This adds build complexity (two CMake targets, two install paths) with no clear benefit for M1. The single-library approach is simpler when the build provides both loader-facing names and the platform dynamic loader preserves one runtime instance.

If a future milestone encounters symbol conflicts, duplicate-load behavior, or binary size concerns, splitting into two libraries is a backward-compatible change.
