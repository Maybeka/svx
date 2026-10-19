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
        return self._unpack(_native.signal_read(self._path), "read")

    def _unpack(
        self, payload: bytes, operation: str, with_context: bool | None = None
    ) -> Any:
        unpack = self._codec.unpack
        if with_context is None:
            with_context = _unpack_accepts_context(unpack)
        if with_context:
            import svtypes
            from .runtime import codec_session

            value, consumed = unpack(payload, svtypes.UnpackContext(codec_session()))
        else:
            value, consumed = unpack(payload)
        if consumed != len(payload):
            raise SVXSignalError(
                self._path,
                operation,
                f"SvTypes codec consumed {consumed} of {len(payload)} bytes",
                "type_mismatch",
            )
        return value

    def subscribe(self) -> SignalSubscription:
        """Seed a cache and subscribe to value changes; no Python callback runs."""
        return SignalSubscription(self)

    def write(self, value: Any) -> None:
        _native.signal_write(self._path, self._pack(value, "write"))

    def force(self, value: Any) -> None:
        _native.signal_force(self._path, self._pack(value, "force"))

    def release(self) -> None:
        _native.signal_release(self._path)


class SignalSubscription:
    """Explicit latest-notified-value cache, not an immediate HDL read or event log.

    Notifications may lag writes within the current scheduling region. Use
    Signal.read() when an immediate read is needed. Close explicitly or use a
    with block; runtime shutdown also removes remaining subscriptions.
    """

    __slots__ = ("_signal", "_id", "_closed", "_with_context")

    def __init__(self, signal: Signal) -> None:
        self._signal = signal
        self._closed = False
        self._with_context = _unpack_accepts_context(signal._codec.unpack)
        self._id = _native.signal_subscribe(signal.path)

    @property
    def path(self) -> str:
        return self._signal.path

    def read(self) -> Any:
        if self._closed:
            raise SVXSignalError(
                self.path, "subscription_read", "signal subscription is closed",
                "subscription_closed",
            )
        return self._signal._unpack(
            _native.signal_subscription_read(self._id),
            "subscription_read", self._with_context,
        )

    def close(self) -> None:
        if not self._closed:
            _native.signal_unsubscribe(self._id)
            self._closed = True

    def __enter__(self) -> SignalSubscription:
        if self._closed:
            raise SVXSignalError(
                self.path, "subscribe", "signal subscription is closed",
                "subscription_closed",
            )
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


def _unpack_accepts_context(unpack: Any) -> bool:
    try:
        inspect.signature(unpack).bind(b"", None)
    except TypeError:
        return False
    return True


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
