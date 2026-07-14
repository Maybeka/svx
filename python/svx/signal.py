"""Small-scale, startup-declared hierarchical HDL signal access."""

from __future__ import annotations

from typing import Any

from . import _native
from .errors import SVXSignalError


def _codec_metadata(codec: Any) -> tuple[int, bool]:
    width = getattr(codec, "width", None)
    signed = getattr(codec, "signed", None)
    state_domain = getattr(codec, "state_domain", None)
    if not isinstance(width, int) or width <= 0:
        raise TypeError("svx.declare_signal() codec must expose a positive integer width")
    if not isinstance(signed, bool):
        raise TypeError("svx.declare_signal() codec must expose boolean signedness")
    if state_domain != "2state":
        raise TypeError(
            "svx.declare_signal() requires a public two-state SvTypes codec; "
            "four-state codecs are not supported yet"
        )
    if not callable(getattr(codec, "pack", None)) or not callable(getattr(codec, "unpack", None)):
        raise TypeError("svx.declare_signal() codec must implement SvTypes pack() and unpack()")
    return width, signed


class Signal:
    """A startup-declared HDL signal backed by one SvTypes codec."""

    __slots__ = ("_path", "_codec", "_width")

    def __init__(self, path: str, codec: Any) -> None:
        self._path = path
        self._codec = codec
        self._width, _ = _codec_metadata(codec)

    @property
    def path(self) -> str:
        return self._path

    def _pack(self, value: Any, operation: str) -> bytes:
        payload = self._codec.pack(value)
        if not isinstance(payload, bytes):
            raise SVXSignalError(
                self._path,
                operation,
                "SvTypes codec pack() must return bytes",
                "type_mismatch",
            )
        expected = (self._width + 7) // 8
        if len(payload) != expected:
            raise SVXSignalError(
                self._path,
                operation,
                f"SvTypes codec returned {len(payload)} bytes; expected {expected}",
                "type_mismatch",
            )
        return payload

    def read(self) -> Any:
        payload = _native.signal_read(self._path)
        value, consumed = self._codec.unpack(payload)
        if consumed != len(payload):
            raise SVXSignalError(
                self._path,
                "read",
                f"SvTypes codec consumed {consumed} of {len(payload)} bytes",
                "type_mismatch",
            )
        return value

    def write(self, value: Any) -> None:
        _native.signal_write(self._path, self._pack(value, "write"))

    def force(self, value: Any) -> None:
        _native.signal_force(self._path, self._pack(value, "force"))

    def release(self) -> None:
        _native.signal_release(self._path)


def declare_signal(path: str, codec: Any) -> Signal:
    """Declare one startup-validated signal in a signal declaration module."""

    if not isinstance(path, str) or not path:
        raise ValueError("svx.declare_signal() path must be a non-empty string")
    width, signed = _codec_metadata(codec)
    _native.signal_declare(path, width, signed)
    return Signal(path, codec)
