# SVX Execution Context — Detailed Design

See [SVX_SPEC.md](../SVX_SPEC.md) Section 4 for the architectural motivation.

## 1. Context Lifecycle

An SVX execution context is a C++ RAII guard pushed onto a thread-local stack.

### 1.1 Creation

A context is created by the C++ runtime on every DPI entry into Python:

| Entry point | Context created? |
|---|---|
| `svx_start` invoking a Python callable | Yes |
| `fork_join` entering each child callable | Yes |
| `fork_join_any` entering each child callable | Yes |
| `fork_join_none` entering each child callable | Yes |
| Any future DPI callback into Python | Yes |

### 1.2 Destruction

The context is destroyed (popped from the stack) when the corresponding DPI call returns to SystemVerilog. There is no explicit user-facing destroy API.

### 1.3 Stack Semantics

Context push/pop is a LIFO stack per OS thread. This supports nested DPI calls if needed in the future, while still allowing a simple "is context present?" check for the common case.

## 2. Implementation

### 2.1 C++ API

```cpp
// svx_runtime/include/svx/context.hpp

namespace svx {

class ExecutionContext {
public:
    ExecutionContext(const char* source_description);
    ~ExecutionContext();

    // Returns true if a valid context exists on the current thread.
    static bool is_active();

    // Returns the topmost context, or nullptr.
    static ExecutionContext* current();

    // Description for error messages: "svx_start('tests.basic_test.main')"
    const char* source() const;

private:
    const char* m_source;
    // Pushed onto thread_local stack in constructor, popped in destructor.
};

} // namespace svx
```

### 2.2 Usage Pattern (C++ DPI callback)

```cpp
// Called from SystemVerilog via DPI when svx_start invokes a Python callable.
void svx_runtime_invoke(PyObject* callable) {
    svx::ExecutionContext ctx("svx_start('<export_name>')");

    PyGILState_STATE gstate = PyGILState_Ensure();
    PyObject* result = PyObject_CallObject(callable, nullptr);
    if (result == nullptr) {
        svx::handle_python_exception(ctx.source());
        return;
    }
    Py_DECREF(result);
    PyGILState_Release(gstate);
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

- The context stack is `thread_local`. Each OS thread has its own independent stack.
- Python threads created by `threading.Thread` or `asyncio` will never have a context on their stack.
- The context check is a cheap pointer/null check — no locking required.

## 5. Testing

Unit tests (runnable without a simulator):

1. Call a primitive without a context → expect `SVXContextError`.
2. Create a context (via C++ test fixture), call a primitive → no error.
3. Destroy the context, call a primitive again → error.
4. Verify context stack nesting: push A, push B, pop B, verify A is still current.
