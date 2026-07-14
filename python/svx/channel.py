from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from . import _native
from .errors import SVXChannelError


SVTYPES_KIND = "svtypes"
SVTYPES_CONTENT_TYPE = "application/x-svtypes"
T = TypeVar("T")


@dataclass(frozen=True)
class Payload:
    data: bytes
    kind: str = "bytes"
    type_name: str = ""
    content_type: str = "application/octet-stream"


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
            payload.data,
        )

    def get_payload(self) -> Payload:
        kind, type_name, content_type, data = _native.channel_get_payload(self.name)
        return Payload(
            data=data,
            kind=kind,
            type_name=type_name,
            content_type=content_type,
        )

    def peek_payload(self) -> Payload:
        kind, type_name, content_type, data = _native.channel_peek_payload(self.name)
        return Payload(
            data=data,
            kind=kind,
            type_name=type_name,
            content_type=content_type,
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
            payload.data,
        )

    def try_get_payload(self) -> Payload | None:
        result = _native.channel_try_get_payload(self.name)
        if result is None:
            return None
        kind, type_name, content_type, data = result
        return Payload(
            data=data,
            kind=kind,
            type_name=type_name,
            content_type=content_type,
        )

    def put(self, item: Any) -> None:
        self.put_payload(_pack_svtypes(item))

    def get(self, cls: type[T]) -> T:
        return _unpack_svtypes(self.get_payload(), cls)

    def peek(self, cls: type[T]) -> T:
        return _unpack_svtypes(self.peek_payload(), cls)

    def try_put(self, item: Any) -> bool:
        return self.try_put_payload(_pack_svtypes(item))

    def try_get(self, cls: type[T]) -> T | None:
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
        return data
    return Payload(
        data=bytes(data),
        kind=kind,
        type_name=type_name,
        content_type=content_type,
    )


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


def _pack_svtypes(item: Any) -> Payload:
    to_bytes = getattr(item, "to_bytes", None)
    if not callable(to_bytes):
        raise SVXChannelError(
            f"typed channel item {type(item).__name__!r} does not provide to_bytes()"
        )
    data = to_bytes()
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise SVXChannelError(
            f"typed channel item {type(item).__name__!r} produced non-bytes payload"
        )
    return Payload(
        data=bytes(data),
        kind=SVTYPES_KIND,
        type_name=_type_name_for(item),
        content_type=SVTYPES_CONTENT_TYPE,
    )


def _unpack_svtypes(payload: Payload, cls: type[T]) -> T:
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

    item = cls()
    from_bytes = getattr(item, "from_bytes", None)
    if not callable(from_bytes):
        raise SVXChannelError(
            f"typed channel class {cls.__name__!r} does not provide from_bytes()"
        )
    from_bytes(payload.data)
    return item
