from __future__ import annotations

import math
from collections.abc import Callable

from . import _native
from .process import ProcessGroup

_UNIT_TO_CODE: dict[str, int] = {
    "s": 0,
    "ms": 1,
    "us": 2,
    "ns": 3,
    "ps": 4,
    "fs": 5,
}


def _to_delay_args(value: int | float, unit: str) -> tuple[float, int]:
    duration = float(value)
    if not math.isfinite(duration):
        raise ValueError(f"svx.delay() value must be finite, got {value!r}")
    if duration < 0:
        raise ValueError(f"svx.delay() value must be non-negative, got {value!r}")
    try:
        unit_code = _UNIT_TO_CODE[unit]
    except KeyError:
        raise ValueError(f"unsupported svx.delay() unit: {unit!r}") from None
    return duration, unit_code


def display(message: object) -> None:
    _native.display(str(message))


def delay(value: int | float, unit: str = "ns") -> None:
    duration, unit_code = _to_delay_args(value, unit)
    _native.delay(duration, unit_code)


def _validate_callables(callables: list[Callable[[], object]] | tuple[Callable[[], object], ...]):
    items = tuple(callables)
    if not items:
        raise ValueError("svx.fork_* requires at least one callable")
    for item in items:
        if not callable(item):
            raise TypeError(f"svx.fork_* expected callables, got {type(item).__name__}")
    return items


def fork_join(callables: list[Callable[[], object]] | tuple[Callable[[], object], ...]) -> ProcessGroup:
    return ProcessGroup(_native.fork_join(_validate_callables(callables)))


def fork_join_any(callables: list[Callable[[], object]] | tuple[Callable[[], object], ...]) -> ProcessGroup:
    return ProcessGroup(_native.fork_join_any(_validate_callables(callables)))


def fork_join_none(callables: list[Callable[[], object]] | tuple[Callable[[], object], ...]) -> ProcessGroup:
    return ProcessGroup(_native.fork_join_none(_validate_callables(callables)))
