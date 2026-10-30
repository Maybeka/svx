# Simulator Process Scheduling

Public fork/join, cancellation and handle semantics belong to the
[API Reference](../SVX_API_REFERENCE.md). Runnable timing and cleanup examples
are indexed in [Examples](../../examples/README.md).

## Dispatch Path

```text
Python fork primitive
  -> native PythonProcess objects and group
  -> exported fork_svx task
  -> SV forked processes publish their indices
  -> svx_process__exec enters each Python callable
```

The simulator owns runnable order and time. Each callable has a distinct
CPython evaluator state, as described in [State Isolation](gil_management.md).
Siblings have no guaranteed execution order. Blocking a Python callable in an
SV primitive yields to the simulator, not to a Python scheduler.

## Startup And Completion

The SV implementation uses a zero-delay yield before returning a join-none
group so children can enter `start_process` and publish their process indices.
It does not implement a separate startup acknowledgement protocol. Completion
and group waits use the SV process/event machinery; group status is derived
from its children rather than from the lifetime of a Python handle.

## Cooperative Stop

SVX stop requests wake cancellation-aware primitives. Their Python frames unwind
through `finally`, while the SV supervision scope handles descendant cleanup.
This is not arbitrary Python stack destruction or a way to interrupt every
foreign task. A non-cooperative user SV task must return before join completes.
Externally disabling a DPI task follows the separate disable acknowledgement
path described by the API. Do not infer cancellation merely from a lost handle.
