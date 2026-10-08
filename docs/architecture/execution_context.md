# SVX Execution Context — Detailed Design

See [SVX_SPEC.md](../SVX_SPEC.md) Section 4 for the architectural motivation.

## 1. Context Lifecycle

An SVX execution context is a C++ RAII guard associated with the current
CPython `PyThreadState`. Multiple simulated processes can suspend on the same
OS thread, so an OS-thread-local stack cannot identify the active Python process.

### 1.1 Creation

A context is created when the C++ runtime enters an application callable, not
merely because a DPI routine imports a module or initializes Python:

| Entry point | Context created? |
|---|---|
| `svx_start` invoking a Python callable | Yes |
| `fork_join` entering each child callable | Yes |
| `fork_join_any` entering each child callable | Yes |
| `fork_join_none` entering each child callable | Yes |
| Inheritance method and constructor callbacks | Yes |
| `svx_load` importing a module | No new application context |

Module top-level code may register exports and declare types, but must not use
simulator primitives merely because it was imported by `svx_load`. Put timed
work in an exported entry or another simulator-owned application callback.

### 1.2 Destruction

The context is destroyed (popped from the stack) when the corresponding DPI call returns to SystemVerilog. There is no explicit user-facing destroy API.

### 1.3 Stack Semantics

Nested contexts retain a previous-context link per `PyThreadState`. The guard
restores that link on exit. Before Python resumes after an SV task, the native
wrapper restores the suspended process's thread state. Nested inheritance
callbacks use the same mechanism; task/function restrictions are additionally
tracked by `python/svx/callback_context.py`.

## 2. Implementation

### 2.1 C++ API

```cpp
// svx_runtime/include/svx/context.hpp

namespace svx {

class ExecutionContext {
public:
    explicit ExecutionContext(std::string source, int process_index = -1);
    ~ExecutionContext();

    // Returns true if a valid context exists on the current thread.
    static bool is_active();

    static PyThreadState* current_thread_state();
    static int current_process_index();
    static void restore(PyThreadState* thread_state);

    // Description for error messages: "svx_start('tests.basic_test.main')"
    const char* source() const;

    PyThreadState* thread_state() const;
};

} // namespace svx
```

### 2.2 Usage Pattern (C++ DPI callback)

```cpp
// Called from SystemVerilog via DPI when svx_start invokes a Python callable.
void svx_runtime_invoke(PyObject* callable) {
    svx::ExecutionContext ctx("svx_start('<export_name>')");

    // The caller has already attached the correct CPython state and holds the GIL.
    PyObject* result = PyObject_CallObject(callable, nullptr);
    if (result == nullptr) {
        svx::handle_python_exception(ctx.source());
        return;
    }
    Py_DECREF(result);
    // ctx destroyed here — context no longer active.
}
```

### 2.3 Validation in Python Primitives

Every SVX primitive in `python/svx/primitives.py` validates user-facing arguments and delegates to a C extension that checks the native context:

```python
def delay(value, unit="ns"):
    duration, unit_code = _to_delay_args(value, unit)
    _svx_native.delay(duration, unit_code)  # raises SVXContextError if no context
```

The C extension wrapper:

```cpp
static PyObject* svx_native_delay(PyObject* self, PyObject* args) {
    if (!svx::ExecutionContext::is_active()) {
        PyErr_SetString(SVXContextError, "svx.delay() may only be called "
            "from an SVX simulator-owned execution context");
        return nullptr;
    }
    // ... perform delay ...
}
```

## 3. Python Exception Contract

When `is_active()` returns false, the primitive must:

1. Raise `svx.SVXContextError` (a subclass of `RuntimeError`).
2. Not attempt any DPI/VPI call.
3. Not leak simulator state.

The error message should name the specific primitive that was called and the rule violated:

```
svx.delay() may only be called from an SVX simulator-owned execution context
svx.display() may only be called from an SVX simulator-owned execution context
svx.fork_join() may only be called from an SVX simulator-owned execution context
```

## 4. Thread Safety

For task-method bridges, the native task disable result is separate from the
method's `ok` output and response payload. The Python bridge restores its saved
thread state and releases payloads before raising cancellation. Python wrapper
code must preserve that exception rather than converting it to `SVXRemoteError`.
An imported Python task callback unwinds its context and removes its cycle-check
frame before acknowledging disable and returning the native disable code. Only
the expected cancellation exception is cleared; an ordinary cleanup exception
continues through the error policy.

- The native map is keyed by `PyThreadState*` and accessed while Python holds the GIL.
- A user-created Python thread has no simulator-owned entry context and cannot call simulator services.
- `asyncio` is not an SVX scheduling path; callbacks must be synchronous ordinary functions.
- Native context validity and the Python function-callback guard enforce different
  conditions: simulator ownership versus legality of task/wait operations.

## 5. Testing

Unit tests (runnable without a simulator):

1. Call a primitive without a context → expect `SVXContextError`.
Native context/process switching requires simulator integration evidence, not
only Python mocks. The fork, disable/scope, and nested inheritance regressions
exercise suspension/restoration. Function-callback tests separately cover
rejection of task and delay operations. These are distinct verification scopes.
