"""Small-scale, startup-declared hierarchical HDL signal access."""

from __future__ import annotations

import inspect
from typing import Any

from . import _native
from .errors import SVXSignalError


def _codec_metadata(codec: Any) -> tuple[int, bool, str, str, str, int]:
    width = getattr(codec, "width", None)
    signed = getattr(codec, "signed", None)
    state_domain = getattr(codec, "state_domain", None)
    if not isinstance(width, int) or width <= 0:
        raise TypeError("svx.declare_signal() codec must expose a positive integer width")
    if signed is None and state_domain == "4state":
        signed = False
    if not isinstance(signed, bool):
        raise TypeError("svx.declare_signal() codec must expose boolean signedness")
    if state_domain not in {"2state", "4state"}:
        raise TypeError(
            "svx.declare_signal() requires a public two-state or four-state SvTypes codec"
        )
    if not callable(getattr(codec, "pack", None)) or not callable(getattr(codec, "unpack", None)):
        raise TypeError("svx.declare_signal() codec must implement SvTypes pack() and unpack()")
    try:
        import svtypes

        descriptor = svtypes.encoding_descriptor(codec)
    except Exception as error:
        raise TypeError(
            f"svx.declare_signal() cannot obtain a public SvTypes encoding descriptor: {error}"
        ) from error
    return (
        width,
        signed,
        state_domain,
        descriptor.unified_type_name,
        descriptor.encoding_fingerprint_hex,
        descriptor.binary_format_version,
    )


class Signal:
    """A startup-declared HDL signal backed by one SvTypes codec."""

    __slots__ = ("_path", "_codec", "_width")

    def __init__(self, path: str, codec: Any) -> None:
        self._path = path
        self._codec = codec
        self._width, _, _, _, _, _ = _codec_metadata(codec)

    @property
    def path(self) -> str:
        return self._path

    def _pack(self, value: Any, operation: str) -> bytes:
        import svtypes
        from .runtime import codec_session

        context = svtypes.PackContext(codec_session())
        pack = self._codec.pack
        try:
            inspect.signature(pack).bind(value, context)
        except TypeError:
            payload = pack(value)
        else:
            payload = pack(value, context)
        if not isinstance(payload, bytes):
            raise SVXSignalError(
                self._path,
                operation,
                "SvTypes codec pack() must return bytes",
                "type_mismatch",
            )
        state_domain = getattr(self._codec, "state_domain")
        expected = (self._width + 7) // 8 * (3 if state_domain == "4state" else 1)
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
        import svtypes
        from .runtime import codec_session

        context = svtypes.UnpackContext(codec_session())
        unpack = self._codec.unpack
        try:
            inspect.signature(unpack).bind(payload, context)
        except TypeError:
            value, consumed = unpack(payload)
        else:
            value, consumed = unpack(payload, context)
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
    width, signed, state_domain, canonical_id, fingerprint, version = _codec_metadata(codec)
    _native.signal_declare(
        path,
        width,
        signed,
        state_domain,
        canonical_id,
        fingerprint,
        version,
    )
    return Signal(path, codec)
