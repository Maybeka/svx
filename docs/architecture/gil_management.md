# CPython State Isolation

This note owns the evaluator-state mechanism. Legal application entry points
are specified in [Execution Context](execution_context.md); public cancellation
and process behavior are in the [API Reference](../SVX_API_REFERENCE.md).

## Simulator-Owned Execution

One embedded CPython interpreter belongs to the simulator process. Simulated
processes can suspend in exported SV tasks and resume on the same host thread,
including in an order different from nested host call returns. They are not
Python threads or asyncio tasks. A single evaluator state cannot safely contain
all those suspended Python frames.

Each `PythonProcess` owns a `PyThreadState`. Entry swaps to that state; a native
primitive saves the caller's state before entering SV and restores it before
returning to Python. `ExecutionContext` is associated with the Python state,
not merely with the host thread. This is why a host-thread-local call stack
alone is insufficient.

## Inheritance Callbacks

An SV-to-Python inheritance callback allocates its own evaluator state. Callback
stacks are keyed by the SV process context ID, so unrelated SV processes do not
inherit one another's receiver, function restriction or cycle stack. Nested calls
copy the appropriate logical Python context; synchronous constructor callbacks
retain their caller's capture context.

On callback exit, the runtime clears that callback's state and switches to the
runtime idle state before deleting it. It must not restore an arbitrary saved
state belonging to an unrelated, now suspended callback. The next returning
native primitive restores its own caller state. This supports independent task
callbacks resuming in non-LIFO order while preserving legal `super()` reentry.

The implementation is in `svx_runtime/src/context.cpp`, `process.cpp` and
`python_bindings.cpp`; this document deliberately does not copy their C++ ABI.

## GIL Boundary

The runtime does not treat an exported SV task as an ordinary OS-thread blocking
call surrounded by `PyEval_SaveThread()` / `PyEval_RestoreThread()`. Another
simulated process can reenter Python on the same host thread during that task.
Evaluator attachment and explicit state restoration follow simulated execution.
Foreign entry acquires the GIL only when no Python evaluator is attached.

These states are internal implementation machinery, not permission to call SVX
from application-created threads. Shutdown releases runtime-owned application
state but retains the interpreter until simulator exit; see the API contract.
