# SVX Concurrency Design — Fork/Join Semantics

See [SVX_SPEC.md](../SVX_SPEC.md) Section 3 and Section 8.

## 1. Scheduling Model

All simulation concurrency is owned by the SystemVerilog simulator. Python code describes concurrency structure; the SV kernel schedules execution.

```
Python code            SVX Runtime (C++)          SystemVerilog Kernel
─────────────         ─────────────────          ─────────────────────
svx.fork_join([       svx_fork_join()            fork_svx task
  child_a,            ─────────────────────────→  fork
  child_b,                                          child_a process
  child_c                                           child_b process
])                                                  child_c process
                     ← wait for all complete ──   join
                     return to Python
```

## 2. fork_join Semantics

```
svx.fork_join(callables: list[Callable]) -> None
```

### 2.1 Behavior

1. Parent calls `svx.fork_join([A, B, C])`.
2. Runtime creates one SV process per callable.
3. Each SV process independently enters its Python callable through a DPI callback.
4. Each child receives its own SVX execution context.
5. **Parent blocks until ALL children have completed.**
6. Parent's SVX context is suspended for the duration; CPython process state is preserved and restored as described in [gil_management.md](gil_management.md).
7. Blocking is achieved via SV `wait fork` statement on the SV side.

### 2.2 Ordering

- **No execution ordering is guaranteed between siblings.** The SV kernel schedules child processes arbitrarily.
- **All children are guaranteed to have completed when `fork_join` returns.**
- If a child calls `delay`, the SV kernel may schedule other children during the delay.

### 2.3 Error Handling

- If any child raises an uncaught exception, the default fatal policy applies (see [error_policy.md](error_policy.md)).
- Exception in one child does not immediately terminate siblings unless the policy mandates simulation termination.
- Under the default `FATAL` policy, the first uncaught exception terminates simulation.

## 3. fork_join_any Semantics

```
svx.fork_join_any(callables: list[Callable]) -> ProcessGroup
```

### 3.1 Behavior

1. Parent calls `svx.fork_join_any([A, B, C])`.
2. Runtime creates one SV process per callable.
3. **Parent blocks until the FIRST child completes.**
4. Remaining children continue running.
5. Blocking is achieved via SV `@ev` event trigger on first completion.
6. A `ProcessGroup` handle is returned for all children, including the completed child and any children still running.

### 3.2 Remaining Children

**Milestone 1 default policy**: Remaining children continue executing. The returned `ProcessGroup` lets the caller inspect, await, or kill the remaining children.

If a user needs to kill remaining children after `fork_join_any`, they can use the returned group:

```python
# Controlled fork_join_any behavior:
group = svx.fork_join_any([child_a, child_b, child_c])
group.kill_running()
```

### 3.3 Future Refinement (Post-M1)

A post-M1 refinement may add an optional policy argument or an explicit `svx.disable_fork()` equivalent to clean up remaining children automatically.

## 4. fork_join_none Semantics

```
svx.fork_join_none(callables: list[Callable]) -> ProcessGroup
```

### 4.1 Behavior

1. Parent calls `group = svx.fork_join_none([A, B, C])`.
2. Runtime creates one SV process per callable.
3. **Parent returns immediately** after processes are created (SV `fork ... join_none`).
4. A `ProcessGroup` handle is returned.

### 4.1.1 Child Startup Synchronization

Milestone 1 uses a zero-delay scheduler yield (`#0`) before `fork_svx` returns
for `FORK_JOIN_NONE`. This gives forked child processes a delta cycle to enter
`start_process`, call `set_proc_index`, and publish their simulator process
indices back to C++.

This is an implementation shortcut, not the final protocol.

The production mechanism should use an explicit event/ack handshake:

1. `fork_svx` computes the number of non-null child process handles.
2. Each child calls `set_proc_index` when it starts.
3. Each child increments a started counter or triggers a started event.
4. The parent waits until every child has acknowledged startup.
5. `fork_svx` returns a `ProcessGroup` whose children all have valid simulator
   process indices.

This future handshake avoids relying on delta-cycle scheduling behavior for
handle publication.

### 4.2 ProcessGroup API (M1)

```python
class ProcessGroup:
    def status(self) -> ProcessStatus:
        """Return aggregate status of all children.
        Returns RUNNING if any child is still running or waiting,
        KILLED if no child is running and at least one child was killed,
        FINISHED if all children completed normally."""

    def await_(self) -> None:
        """Block until all children have completed.
        Uses trailing underscore because 'await' is a Python keyword."""

    def kill(self) -> None:
        """Kill all children that are still running."""

    def kill_running(self) -> None:
        """Alias for kill(); provided for fork_join_any readability."""

class ProcessStatus(Enum):
    FINISHED = "finished"
    RUNNING = "running"
    KILLED = "killed"
```

### 4.3 Implementation Notes

- Each child maps to an SV `process` handle stored in `svx_process_manager`.
- The process manager assigns integer indices, shared with the C++ side via `svx_process__set_svobj_idx`.
- `status()` aggregates across all children: returns `RUNNING` if any child is still running or waiting, `KILLED` if no child is running and at least one child was killed, and `FINISHED` only if all children completed normally.
- `kill()` iterates all children and calls `process::kill()` on the SV side.
- `await_()` blocks the calling SV process via `process::await()` for each child.

## 5. Process Lifecycle States

```
NOT_CREATED ──→ RUNNING ──→ FINISHED
                    │
                    ├──→ WAITING ──→ RUNNING
                    │
                    ├──→ SUSPENDED ──→ RUNNING
                    │
                    └──→ KILLED
                              │
                              └──→ REMOVED
```

- `NOT_CREATED`: Index allocated but process not yet started.
- `RUNNING`: Process is actively executing or schedulable.
- `WAITING`: Process is blocked on a timing or event control (e.g., inside `delay`).
- `SUSPENDED`: Process was explicitly suspended via `suspend()` (post-M1).
- `FINISHED`: Process completed normally.
- `KILLED`: Process was terminated via `kill()`.
- `REMOVED`: Process handle was removed from the manager.

## 6. Constraints

- SVX_MAX_FORK_NUM = 32. Maximum number of callables in a single `fork_join*` call.
- Nested fork/join is supported: a child callable may call `fork_join*` to create grandchildren.
- All descendants inherit the same GIL serialization rules from [gil_management.md](gil_management.md).

## 7. Testing

1. `fork_join` with two children that each call `delay(10, "ns")` — verify both complete and total time is ~10ns (parallel).
2. `fork_join_none` → `group.status()` returns RUNNING → `delay(100, "ns")` → `group.status()` returns FINISHED.
3. `fork_join_none` → `group.kill()` → `group.status()` returns KILLED.
4. `fork_join_any` with child A (delay 5ns) and child B (delay 10ns) — verify parent returns after ~5ns.
5. Nested fork: parent calls `fork_join_none([child])`, child calls `fork_join([grandchild_a, grandchild_b])` — verify both grandchildren complete before child completes.
