"""Internal synchronous constructor segments; no user coroutine API."""

from collections.abc import Callable
from dataclasses import dataclass
from contextvars import copy_context
import threading
from typing import Any

from .errors import SVXInheritanceError


@dataclass
class _Segment:
    continuation: Any
    thread_id: int
    suspended: bool = False
    owner: Any = None


class ConstructorContinuations:
    """Retain one original initializer invocation per receiver and boundary."""

    def __init__(self):
        self._segments: dict[tuple[int, str], _Segment] = {}

    @property
    def pending_count(self) -> int:
        return len(self._segments)

    @staticmethod
    def _greenlet_api():
        try:
            from greenlet import getcurrent, greenlet
        except ImportError as error:
            raise SVXInheritanceError(
                "natural cross-language construction requires greenlet"
            ) from error
        return getcurrent, greenlet

    def prepare(self, receiver: int, boundary: str, initializer: Callable[[], None], *, owner: Any = None) -> bytes:
        key = (receiver, boundary)
        if key in self._segments:
            raise SVXInheritanceError(f"constructor segment already exists: {key}")
        if any(r == receiver and segment.owner is not owner for (r, _), segment in self._segments.items()):
            raise SVXInheritanceError(f"constructor receiver changed Python identity: {receiver}")
        _, greenlet = self._greenlet_api()
        continuation = greenlet(initializer)
        continuation.gr_context = copy_context()
        segment = _Segment(continuation, threading.get_ident(), owner=owner)
        self._segments[key] = segment
        try:
            payload = segment.continuation.switch()
            if segment.continuation.dead or not segment.suspended or not isinstance(payload, bytes):
                raise SVXInheritanceError(f"constructor did not reach its mirror boundary: {key}")
            return payload
        except BaseException:
            self._segments.pop(key, None)
            raise

    def suspend(self, receiver: int, boundary: str, payload: bytes) -> None:
        key = (receiver, boundary)
        segment = self._segments.get(key)
        getcurrent, _ = self._greenlet_api()
        if (segment is None or segment.continuation is not getcurrent()
                or segment.suspended or not isinstance(payload, bytes)):
            raise SVXInheritanceError(f"invalid constructor mirror suspension: {key}")
        segment.suspended = True
        segment.continuation.parent.switch(payload)

    def resume(self, receiver: int, boundary: str, *, owner: Any = None) -> None:
        key = (receiver, boundary)
        segment = self._segments.get(key)
        if segment is None or not segment.suspended:
            raise SVXInheritanceError(f"constructor segment is not suspended: {key}")
        if segment.owner is not owner:
            raise SVXInheritanceError(f"constructor receiver changed Python identity: {receiver}")
        if segment.thread_id != threading.get_ident():
            raise SVXInheritanceError(f"constructor segment belongs to another thread: {key}")
        try:
            segment.continuation.switch()
            if not segment.continuation.dead:
                raise SVXInheritanceError(f"constructor segment did not complete: {key}")
        finally:
            self._segments.pop(key, None)

    def abort(self, receiver: int, error: BaseException) -> None:
        """Cooperatively unwind all suspended portions of a failed receiver."""
        keys = [key for key in self._segments if key[0] == receiver]
        if any(self._segments[key].thread_id != threading.get_ident() for key in keys):
            raise SVXInheritanceError(f"constructor receiver belongs to another thread: {receiver}")
        for key in reversed(keys):
            segment = self._segments.pop(key)
            try:
                segment.continuation.throw(error)
            except BaseException as cleanup_error:
                if cleanup_error is not error:
                    error.add_note(f"constructor unwind {key}: {cleanup_error}")
