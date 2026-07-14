# SVX CPython State Management — Detailed Design

See [SVX_SPEC.md](../SVX_SPEC.md) Section 3.2.

## 1. Model

SVX uses one embedded CPython interpreter per simulator process.

SystemVerilog simulators schedule many simulated processes on one
host thread. A Python callable may block inside an exported SV task such as
`delay_svx`, while another simulated process re-enters Python on the same host
thread.

That means SVX cannot model forked Python execution as normal OS-thread Python
concurrency, and it also cannot use one CPython thread state for all simulated
processes. Multiple suspended Python call stacks on one host thread corrupt the
interpreter state.

SVX therefore uses:

- one CPython interpreter
- one CPython `PyThreadState` per simulator-owned Python process
- explicit `PyThreadState_Swap()` when the simulator enters or resumes a Python
  process
- no Python `async`/`await`
- no user-created Python threads as simulator-visible processes

The simulator remains the scheduler. CPython thread states are used only to keep
interpreter frame state separate for each simulator-owned Python process.

## 2. Native Boundaries

There are two native boundaries.

### 2.1 SV-To-Python Entry

SystemVerilog calls C++, and C++ enters a Python callable.

For `svx_start`, SVX uses the main interpreter thread state.

For forked processes, SVX creates a dedicated `PyThreadState` for each
`PythonProcess`. On process entry:

```cpp
PyThreadState* prev = PyThreadState_Swap(process_thread_state);
ExecutionContext ctx("svx_process");
PyObject_CallNoArgs(callable);
PyThreadState_Swap(prev);
```

### 2.2 Python Primitive Call Into SV

Python calls a native `_svx_native` primitive such as `svx.delay`.

The primitive validates that the current CPython thread state has an active SVX
execution context. It then calls the exported SV task directly:

```cpp
const ExecutionContext* ctx = ExecutionContext::current();
PyThreadState* process_state = ctx->thread_state();
delay_svx(duration, unit_code);
ExecutionContext::restore(process_state);
```

The restore step is required because the simulator may run another simulated
process while the current process is blocked in `delay_svx`. When the blocked
process resumes, SVX restores the correct CPython thread state before returning
to Python bytecode.

## 3. Execution Context Tracking

An `ExecutionContext` is associated with the current `PyThreadState`, not just
with an OS thread.

This is important because a simulator may switch between multiple simulated process
stacks on the same OS thread.

Context validation therefore checks:

```text
current PyThreadState -> active SVX ExecutionContext
```

It does not rely on a simple thread-local stack.

## 4. Why SVX Does Not Release The GIL Around SV Tasks In M1

The initial design considered releasing the GIL with `PyEval_SaveThread()`
before blocking SV tasks. That is the right pattern for normal OS-threaded
blocking C calls, but it is not the right model for simulator process
switching.

Another simulated process can re-enter Python on the same host thread
while the first simulated process is suspended inside an exported SV task. SVX
must preserve and restore the correct CPython thread state for each simulated
process. Releasing the GIL as if the call were a normal OS-thread block can
leave the interpreter attached to the wrong suspended frame when simulation
control returns.

For M1, SVX keeps Python execution simulator-thread-owned and uses
`PyThreadState_Swap()` to separate simulated Python process state.

## 5. Fork/Join Interaction

When `svx.fork_join([A, B])` is called:

1. The parent Python process calls the native fork primitive.
2. SVX creates one `PythonProcess` per callable.
3. Each `PythonProcess` owns a distinct `PyThreadState`.
4. SV creates simulator processes with `fork`.
5. Each simulator process enters C++ through `svx_process__exec`.
6. C++ swaps to that process's `PyThreadState` and invokes the Python callable.
7. If the callable calls `svx.delay`, the simulator may suspend that process.
8. Another simulator process may enter Python; C++ swaps to that process's
   `PyThreadState`.
9. When the delayed process resumes, the native primitive restores its original
   `PyThreadState` before returning to Python.

This gives Python-authored simulation concurrency without Python-native
scheduling.

## 6. Verified Behavior

The M1 fork example verifies:

- `fork_join` with two delayed children completes at the maximum child delay,
  not the sum.
- `fork_join_any` returns when the fast child completes.
- `fork_join_any` remaining children can be killed through the returned group.
- `fork_join_none` returns after children are scheduled and process indices are
  assigned.
- `ProcessGroup.await_()` waits for a background delayed child.

## 7. Constraints

SVX primitive APIs remain illegal from user-created Python threads,
`asyncio` tasks, multiprocessing workers, or subprocesses.

The CPython thread states described here are internal SVX runtime machinery.
They do not make Python-native concurrency part of the SVX user model.
