"""Optional simulator-owned waveform recording."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
import os

from . import _native
from .callback_context import require_blocking_operations_allowed
from .errors import SVXWaveformError


class State(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


_CAPABILITIES = frozenset({"string_scopes", "dynamic_depth", "pause_resume",
                           "switch_file", "add_scope", "finish_restart"})


def capabilities() -> frozenset[str]:
    """Return available operations; importing SVX never loads a waveform backend."""
    try:
        enabled = _native.waveform_available()
    except ModuleNotFoundError as error:
        if error.name != "_svx_native":
            raise
        enabled = False
    return _CAPABILITIES if enabled else frozenset()


def state() -> State:
    """Return the shared recording state from the active native runtime."""
    return State(_native.waveform_state())


def _scope(path: str, depth: int) -> tuple[str, int]:
    if not isinstance(path, str) or not path or "\0" in path:
        raise ValueError("waveform scope must be a nonempty string without NUL")
    if isinstance(depth, bool) or not isinstance(depth, int):
        raise TypeError("waveform depth must be an integer")
    if not 0 <= depth <= 2**31 - 1:
        raise ValueError("waveform depth must be between 0 and 2147483647")
    return path, depth


def _file(path: str | os.PathLike[str]) -> str:
    value = os.fspath(path)
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError("waveform filename must be nonempty text without NUL")
    return value


def _require() -> None:
    require_blocking_operations_allowed("svx.waveform")
    if not capabilities():
        raise SVXWaveformError("no compatible waveform bridge is available")


def begin(path: str | os.PathLike[str], *, scopes: Iterable[tuple[str, int]]) -> None:
    """Start a fresh recording with all requested module scopes and depths."""
    filename = _file(path)
    selected = tuple(_scope(scope, depth) for scope, depth in scopes)
    if not selected:
        raise ValueError("waveform begin requires at least one scope")
    _require()
    _native.waveform_begin(filename, selected)


def _command(operation: int, path: str = "", depth: int = 0) -> None:
    _require()
    _native.waveform_command(operation, path, depth)


def pause() -> None:
    """Pause recording without stopping simulation."""
    _command(3)


def resume() -> None:
    """Resume a paused recording without recovering its missing history."""
    _command(4)


def flush() -> None:
    """Flush current waveform buffers without ending recording."""
    _command(5)


def switch_file(path: str | os.PathLike[str]) -> None:
    """Continue the current signal selection in a different output file."""
    _command(6, _file(path))


def add_scope(path: str, depth: int = 0) -> None:
    """Add signals from a module scope; existing selections are not removed."""
    scope, level = _scope(path, depth)
    _command(2, scope, level)


def finish() -> None:
    """Close recording; a later begin starts a fresh selection. Idempotent."""
    _command(7)
