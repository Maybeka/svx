"""SVX adapter for SvTypes' public external-field-storage protocol.

This module deliberately contains no SvTypes value, container, or codec logic.
SvTypes normalizes and packs values before calling the backend; SVX forwards the
opaque binding key, public descriptor metadata, typed path, operation, and
bytes to the generated/native field ABI.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import struct
from typing import Protocol

from .errors import SVXInheritanceError


@dataclass(frozen=True)
class FieldStorageKey:
    """Opaque SvTypes key for one projected SVX object member."""

    object_id: int
    field_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, int) or self.object_id <= 0:
            raise ValueError("SVX field storage object id must be non-zero")
        if not isinstance(self.field_id, str) or not self.field_id:
            raise ValueError("SVX field storage field id must be non-empty")


class FieldTransport(Protocol):
    """Native boundary used by :class:`SVXFieldStorage`."""

    def read_field(
        self,
        object_id: int,
        field_id: str,
        descriptor: str,
        path: str,
    ) -> bytes: ...

    def write_field(
        self,
        object_id: int,
        field_id: str,
        descriptor: str,
        path: str,
        operation: str,
        payload: bytes | None,
    ) -> bytes | None: ...


def _descriptor_wire(descriptor: object) -> str:
    try:
        payload = {
            "unified_type_name": descriptor.unified_type_name,
            "encoding_descriptor": descriptor.encoding_descriptor.to_dict(),
        }
    except AttributeError as error:
        raise TypeError("SVX field storage requires a public SvTypes FieldDescriptor") from error
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _path_wire(path: object) -> str:
    """Serialize only public SvTypes FieldPath segment data."""

    try:
        from svtypes import FieldIndex, FieldKey, FieldMember
    except ImportError as error:  # pragma: no cover - package prerequisite
        raise SVXInheritanceError("SvTypes external field storage is unavailable") from error

    segments = []
    for segment in path:
        if isinstance(segment, FieldMember):
            segments.append({"kind": "member", "name": segment.name})
        elif isinstance(segment, FieldIndex):
            segments.append({"kind": "index", "index": segment.index})
        elif isinstance(segment, FieldKey):
            segments.append(
                {"kind": "key", "encoded": base64.b64encode(segment.encoded).decode("ascii")}
            )
        else:
            raise TypeError(f"unsupported public SvTypes field path segment {type(segment).__name__}")
    return json.dumps(segments, separators=(",", ":"))


_FIELD_OPERATION_CODES = {
    "read": 0,
    "set": 1,
    "insert": 2,
    "delete": 3,
    "append": 4,
    "pop": 5,
    "resize": 6,
}


def _field_operation_wire(path: str, operation: str, payload: bytes | None) -> bytes:
    """Encode an internal, versioned envelope around public SvTypes metadata.

    SvTypes remains the value contract: its path segments, operation names and
    already-packed leaf bytes are copied without reinterpretation.  This small
    envelope is only the SVX native dispatcher framing needed to select a
    generated, concrete SystemVerilog lvalue.
    """

    try:
        segments = json.loads(path)
    except json.JSONDecodeError as error:  # pragma: no cover - _path_wire owns input
        raise SVXInheritanceError("invalid internal SVX field path encoding") from error
    if operation not in _FIELD_OPERATION_CODES:
        raise SVXInheritanceError(f"unsupported SvTypes field operation {operation!r}")

    data = bytearray(b"SVXF")
    data.append(1)
    data.append(_FIELD_OPERATION_CODES[operation])
    data.extend(struct.pack("<I", len(segments)))
    for segment in segments:
        kind = segment.get("kind") if isinstance(segment, dict) else None
        if kind == "member":
            value = segment.get("name")
            if not isinstance(value, str):
                raise SVXInheritanceError("invalid SvTypes member path segment")
            encoded = value.encode("utf-8")
            data.append(1)
        elif kind == "index":
            value = segment.get("index")
            if not isinstance(value, int) or value < 0:
                raise SVXInheritanceError("invalid SvTypes index path segment")
            encoded = struct.pack("<Q", value)
            data.append(2)
        elif kind == "key":
            value = segment.get("encoded")
            if not isinstance(value, str):
                raise SVXInheritanceError("invalid SvTypes key path segment")
            try:
                encoded = base64.b64decode(value, validate=True)
            except ValueError as error:
                raise SVXInheritanceError("invalid SvTypes encoded key path segment") from error
            data.append(3)
        else:
            raise SVXInheritanceError("unsupported SvTypes field path segment")
        data.extend(struct.pack("<I", len(encoded)))
        data.extend(encoded)
    data.append(0 if payload is None else 1)
    if payload is not None:
        data.extend(struct.pack("<I", len(payload)))
        data.extend(payload)
    return bytes(data)


class _NativeFieldTransport:
    def read_field(self, object_id: int, field_id: str, descriptor: str, path: str) -> bytes:
        from . import _native

        if path != "[]":
            return _native.inheritance_call_sv(
                object_id,
                f"{field_id}@svx_field_operation",
                _field_operation_wire(path, "read", None),
            )
        # Reuse the manifest dispatcher rather than creating a second C->SV
        # route. The generated endpoint validates the concrete field identity.
        return _native.inheritance_call_sv(object_id, f"{field_id}@svx_field_read", b"")

    def write_field(
        self,
        object_id: int,
        field_id: str,
        descriptor: str,
        path: str,
        operation: str,
        payload: bytes | None,
    ) -> bytes | None:
        from . import _native

        if path == "[]" and operation == "set":
            if payload is None:
                raise SVXInheritanceError("SVX field set requires SvTypes payload bytes")
            _native.inheritance_call_sv(object_id, f"{field_id}@svx_field_set", payload)
            return None
        _native.inheritance_call_sv(
            object_id,
            f"{field_id}@svx_field_operation",
            _field_operation_wire(path, operation, payload),
        )
        return None


class SVXFieldStorage:
    """One session-scoped backend instance used by selected mirror fields."""

    def __init__(self, transport: FieldTransport | None = None) -> None:
        self._transport = transport or _NativeFieldTransport()
        self._closed = False

    def close(self) -> None:
        self._closed = True

    def read(self, key: object, descriptor: object, path: object) -> bytes:
        if self._closed:
            raise SVXInheritanceError("SVX field storage session is closed")
        binding = self._binding(key)
        result = self._transport.read_field(
            binding.object_id,
            binding.field_id,
            _descriptor_wire(descriptor),
            _path_wire(path),
        )
        if not isinstance(result, bytes):
            raise SVXInheritanceError("SVX native field read returned non-bytes")
        return result

    def write(
        self,
        key: object,
        descriptor: object,
        path: object,
        operation: object,
        payload: bytes | None,
    ) -> bytes | None:
        if self._closed:
            raise SVXInheritanceError("SVX field storage session is closed")
        if payload is not None and not isinstance(payload, bytes):
            raise TypeError("SVX field storage payload must be bytes or None")
        binding = self._binding(key)
        operation_name = getattr(operation, "value", operation)
        if not isinstance(operation_name, str):
            raise TypeError("SVX field storage operation must be a public FieldOperation")
        result = self._transport.write_field(
            binding.object_id,
            binding.field_id,
            _descriptor_wire(descriptor),
            _path_wire(path),
            operation_name,
            payload,
        )
        if result is not None and not isinstance(result, bytes):
            raise SVXInheritanceError("SVX native field write returned non-bytes")
        return result

    @staticmethod
    def _binding(key: object) -> FieldStorageKey:
        if not isinstance(key, FieldStorageKey):
            raise TypeError("SVX field storage received a foreign opaque key")
        return key


def bind_projected_fields(
    owner: object,
    object_id: int,
    field_ids: dict[object, str],
    *,
    storage: SVXFieldStorage | None = None,
) -> SVXFieldStorage:
    """Bind selected ordinary SvTypes fields of one mirror instance to SV.

    ``field_ids`` is keyed by the public SvTypes ``FieldIdentity`` objects
    emitted from the manifest. Unselected fields are intentionally omitted and
    remain local to this Python instance.
    """

    if not hasattr(owner, "bind_external_storage"):
        raise TypeError("projected field owner must be a SvTypes SvObject instance")
    backend = storage or SVXFieldStorage()
    keys = {
        identity: FieldStorageKey(object_id, field_id)
        for identity, field_id in field_ids.items()
    }
    owner.bind_external_storage(backend, keys)
    return backend


def projected_field_identities(
    owner: object,
    field_ids_by_name: dict[str, str],
) -> dict[object, str]:
    """Resolve manifest field names to public SvTypes identities for ``owner``.

    ``FieldIdentity`` intentionally names the class that declared the field.
    The manifest is source-language neutral and therefore cannot contain a
    Python class object.  Resolving the declaring class through ordinary MRO
    lookup keeps the generated lifecycle code on public Python and SvTypes
    APIs.  A shadowed field is rejected: it has no stable cross-language field
    identity and SvTypes rejects the same ambiguous shape when binding.
    """

    try:
        from svtypes import FieldIdentity
    except ImportError as error:  # pragma: no cover - package prerequisite
        raise SVXInheritanceError("SvTypes external field storage is unavailable") from error
    if not isinstance(field_ids_by_name, dict):
        raise TypeError("projected field IDs must be a mapping from names to manifest field IDs")

    result: dict[object, str] = {}
    for name, field_id in field_ids_by_name.items():
        if not isinstance(name, str) or not name:
            raise TypeError("projected field name must be a non-empty string")
        if not isinstance(field_id, str) or not field_id:
            raise TypeError("projected field ID must be a non-empty string")
        declaring = [cls for cls in type(owner).mro() if name in vars(cls)]
        if len(declaring) != 1:
            raise SVXInheritanceError(
                f"projected field {type(owner).__name__}.{name} has no unique declaring class"
            )
        result[FieldIdentity(declaring[0], name)] = field_id
    return result
