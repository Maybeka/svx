from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, TypeVar

from . import _native
from .errors import SVXChannelError


SVTYPES_KIND = "svtypes"
SVTYPES_CONTENT_TYPE = "application/x-svtypes"
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
T = TypeVar("T")


@dataclass(frozen=True)
class Payload:
    data: bytes
    kind: str = "bytes"
    type_name: str = ""
    content_type: str = "application/octet-stream"
    unified_type_name: str = ""
    encoding_fingerprint: str = ""
    binary_format_version: int = 0


class Channel:
    def __init__(self, name: str):
        if not isinstance(name, str) or not name:
            raise ValueError("svx.channel() requires a non-empty channel name")
        self.name = name

    def put_payload(
        self,
        data: bytes | bytearray | memoryview | Payload,
        *,
        kind: str = "bytes",
        type_name: str = "",
        content_type: str = "application/octet-stream",
    ) -> None:
        payload = _coerce_payload(data, kind, type_name, content_type)
        _native.channel_put_payload(
            self.name,
            payload.kind,
            payload.type_name,
            payload.content_type,
            payload.unified_type_name,
            payload.encoding_fingerprint,
            payload.binary_format_version,
            payload.data,
        )

    def get_payload(self) -> Payload:
        (
            kind,
            type_name,
            content_type,
            unified_type_name,
            encoding_fingerprint,
            binary_format_version,
            data,
        ) = _native.channel_get_payload(self.name)
        return Payload(
            data=data,
            kind=kind,
            type_name=type_name,
            content_type=content_type,
            unified_type_name=unified_type_name,
            encoding_fingerprint=encoding_fingerprint,
            binary_format_version=binary_format_version,
        )

    def peek_payload(self) -> Payload:
        (
            kind,
            type_name,
            content_type,
            unified_type_name,
            encoding_fingerprint,
            binary_format_version,
            data,
        ) = _native.channel_peek_payload(self.name)
        return Payload(
            data=data,
            kind=kind,
            type_name=type_name,
            content_type=content_type,
            unified_type_name=unified_type_name,
            encoding_fingerprint=encoding_fingerprint,
            binary_format_version=binary_format_version,
        )

    def try_put_payload(
        self,
        data: bytes | bytearray | memoryview | Payload,
        *,
        kind: str = "bytes",
        type_name: str = "",
        content_type: str = "application/octet-stream",
    ) -> bool:
        payload = _coerce_payload(data, kind, type_name, content_type)
        return _native.channel_try_put_payload(
            self.name,
            payload.kind,
            payload.type_name,
            payload.content_type,
            payload.unified_type_name,
            payload.encoding_fingerprint,
            payload.binary_format_version,
            payload.data,
        )

    def try_get_payload(self) -> Payload | None:
        result = _native.channel_try_get_payload(self.name)
        if result is None:
            return None
        (
            kind,
            type_name,
            content_type,
            unified_type_name,
            encoding_fingerprint,
            binary_format_version,
            data,
        ) = result
        return Payload(
            data=data,
            kind=kind,
            type_name=type_name,
            content_type=content_type,
            unified_type_name=unified_type_name,
            encoding_fingerprint=encoding_fingerprint,
            binary_format_version=binary_format_version,
        )

    def put(self, item: Any, codec: Any | None = None) -> None:
        self.put_payload(_pack_svtypes(item, codec))

    def get(self, cls: type[T] | Any) -> T:
        return _unpack_svtypes(self.get_payload(), cls)

    def peek(self, cls: type[T] | Any) -> T:
        return _unpack_svtypes(self.peek_payload(), cls)

    def try_put(self, item: Any, codec: Any | None = None) -> bool:
        return self.try_put_payload(_pack_svtypes(item, codec))

    def try_get(self, cls: type[T] | Any) -> T | None:
        payload = self.try_get_payload()
        if payload is None:
            return None
        return _unpack_svtypes(payload, cls)


def channel(name: str) -> Channel:
    return Channel(name)


def _coerce_payload(
    data: bytes | bytearray | memoryview | Payload,
    kind: str,
    type_name: str,
    content_type: str,
) -> Payload:
    if isinstance(data, Payload):
        payload = data
    else:
        payload = Payload(
            data=bytes(data),
            kind=kind,
            type_name=type_name,
            content_type=content_type,
        )
    if len(payload.data) > MAX_PAYLOAD_BYTES:
        raise SVXChannelError(
            f"channel payload has {len(payload.data)} bytes; resource limit is {MAX_PAYLOAD_BYTES}"
        )
    return payload


def _type_name_for(cls_or_obj: Any) -> str:
    if isinstance(cls_or_obj, type):
        return (
            getattr(cls_or_obj, "_svx_type_name", None)
            or getattr(cls_or_obj, "__svx_type_name__", None)
            or cls_or_obj.__name__
        )
    return (
        getattr(cls_or_obj, "_svx_type_name", None)
        or getattr(cls_or_obj, "__svx_type_name__", None)
        or cls_or_obj.__class__.__name__
    )


def _codec_instance(codec_or_type: Any) -> Any:
    from .runtime import codec_session

    if not isinstance(codec_or_type, type):
        return codec_or_type
    try:
        return codec_or_type(session=codec_session())
    except TypeError:
        return codec_or_type()


def _pack_svtypes(item: Any, codec_or_type: Any | None = None) -> Payload:
    codec = item if codec_or_type is None else _codec_instance(codec_or_type)
    pack = getattr(codec, "pack", None)
    if not callable(pack):
        raise SVXChannelError(
            f"typed channel codec {type(codec).__name__!r} does not provide pack()"
        )
    try:
        from .runtime import codec_session
        import svtypes

        context = svtypes.PackContext(codec_session())
        try:
            inspect.signature(pack).bind(item, context)
        except TypeError:
            data = pack(item)
        else:
            data = pack(item, context)
    except Exception as error:
        raise SVXChannelError(
            f"SvTypes encode failed for typed channel item {type(item).__name__!r}: {error}"
        ) from error
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise SVXChannelError(
            f"typed channel item {type(item).__name__!r} produced non-bytes payload"
        )
    try:
        import svtypes

        descriptor = svtypes.encoding_descriptor(
            codec_or_type if codec_or_type is not None else item.__class__
        )
    except Exception as error:
        raise SVXChannelError(
            f"cannot obtain public SvTypes encoding descriptor for {type(item).__name__}: {error}"
        ) from error
    return Payload(
        data=bytes(data),
        kind=SVTYPES_KIND,
        type_name=_type_name_for(
            codec_or_type if codec_or_type is not None else item
        ),
        content_type=SVTYPES_CONTENT_TYPE,
        unified_type_name=descriptor.unified_type_name,
        encoding_fingerprint=descriptor.encoding_fingerprint_hex,
        binary_format_version=descriptor.binary_format_version,
    )


def _unpack_svtypes(payload: Payload, cls: type[T] | Any) -> T:
    expected_type = _type_name_for(cls)
    if payload.kind != SVTYPES_KIND:
        raise SVXChannelError(
            f"expected SvTypes payload kind {SVTYPES_KIND!r}, got {payload.kind!r}"
        )
    if payload.content_type != SVTYPES_CONTENT_TYPE:
        raise SVXChannelError(
            "expected SvTypes content type "
            f"{SVTYPES_CONTENT_TYPE!r}, got {payload.content_type!r}"
        )
    if payload.type_name and payload.type_name != expected_type:
        raise SVXChannelError(
            f"expected SvTypes payload {expected_type!r}, got {payload.type_name!r}"
        )

    try:
        import svtypes

        descriptor = svtypes.EncodingDescriptor(
            payload.unified_type_name,
            bytes.fromhex(payload.encoding_fingerprint),
            payload.binary_format_version,
        )
        from .runtime import codec_session

        codec = _codec_instance(cls)
        context = svtypes.UnpackContext(codec_session())
        checked_unpack = svtypes.checked_unpack
        try:
            inspect.signature(checked_unpack).bind(
                codec, payload.data, descriptor, context
            )
        except TypeError:
            value, consumed = checked_unpack(codec, payload.data, descriptor)
        else:
            value, consumed = checked_unpack(
                codec, payload.data, descriptor, context
            )
    except Exception as error:
        raise SVXChannelError(
            f"SvTypes checked decode failed for channel payload {expected_type!r}: {error}"
        ) from error
    if consumed != len(payload.data):
        raise SVXChannelError(
            f"SvTypes payload {expected_type!r} consumed {consumed} of {len(payload.data)} bytes"
        )
    return value
