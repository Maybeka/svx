"""Generic restrictions for synchronous foreign callback contexts.

Some foreign runtimes invoke Python through a SystemVerilog function.  A
function callback may inspect state but cannot use an SVX operation that waits,
advances simulation time, or starts an SV process.  Generated integrations use
this small context manager around such callbacks.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

from .errors import SVXContextError


_BLOCKING_REASON: ContextVar[str | None] = ContextVar("svx_blocking_reason", default=None)


@contextmanager
def blocking_operations_disallowed(reason: str) -> Iterator[None]:
    """Reject blocking SVX operations while executing a synchronous callback."""

    token = _BLOCKING_REASON.set(reason)
    try:
        yield
    finally:
        _BLOCKING_REASON.reset(token)


def require_blocking_operations_allowed(operation: str) -> None:
    """Raise before an operation can leave a function callback context."""

    reason = _BLOCKING_REASON.get()
    if reason is not None:
        raise SVXContextError(f"{operation} is not allowed while {reason}")


def _release_in_function_context(instance: object) -> None:
    # Guard attribute lookup too: a custom descriptor can execute user code.
    with blocking_operations_disallowed("executing SV function object cleanup"):
        release = getattr(instance, "_svx_release_projected_fields", None)
        if release is not None:
            release()
