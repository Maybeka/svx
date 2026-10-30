# SVX Python↔C++ Binding Mechanism

See the [source map](../SVX_PROJECT_LAYOUT.md) and [native-state model](gil_management.md).

## Current Implementation Boundary

Build recipes are maintained in [shared setup](../../examples/RUNNING_EXAMPLES.md),
and public/private API classification in [the API reference](../SVX_API_REFERENCE.md).

The current root `CMakeLists.txt` builds the runtime with the CPython C API.
When SVX initializes CPython itself, `prepare_runtime` in
`svx_runtime/src/python_runtime.cpp` registers `_svx_native` with
`PyImport_AppendInittab` before `Py_Initialize`; module registration does not
happen simply because the shared library was loaded. Importing the pure-Python
`svx` package does not require loading the native library until a native service
is requested. If an external host already initialized Python, its integration
must make the native module available without loading a second runtime instance.

Context ownership is per CPython thread state, not an OS-thread-local stack;
see [execution_context.md](execution_context.md). Signal and handle services use those same controlled native boundaries.
