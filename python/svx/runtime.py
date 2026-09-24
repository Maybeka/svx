"""SVX runtime compatibility and session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from .errors import SVXError
from ._version import __version__
from ._svtypes_contract import (
    SVTYPES_BINARY_FORMAT_VERSION,
    SVTYPES_GENERATOR_RUNTIME_ABI_VERSION,
    SVTYPES_OBJECT_ENVELOPE_VERSION,
    SVTYPES_PACKAGE_MAJOR_VERSION,
    SVTYPES_REQUIRED_CAPABILITIES,
    SVTYPES_SCHEMA_FORMAT_VERSION,
)


SVX_RUNTIME_ABI_VERSION = 1
SVX_GENERATOR_ABI_VERSION = 2
SVX_MANIFEST_SCHEMA_MAJOR = 2
SVX_FEATURE_BITS = frozenset(
    {
        "checked_svtypes_payloads",
        "codec_sessions",
        "cross_language_inheritance",
        "projected_field_storage",
        "hierarchical_signal_access",
        "remote_references",
    }
)


class RuntimeState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class SvTypesCapabilities:
    package_major_version: int
    schema_format_version: int
    binary_format_version: int
    object_envelope_version: int
    generator_runtime_abi_version: int
    provided: frozenset[str]


_state = RuntimeState.UNINITIALIZED
_codec_session: Any | None = None
_svtypes_capabilities: SvTypesCapabilities | None = None


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        try:
            return value[name]
        except KeyError:
            pass
    try:
        return getattr(value, name)
    except AttributeError as exc:
        raise SVXError(f"SvTypes runtime capability is missing {name!r}") from exc


def _read_svtypes_capabilities() -> SvTypesCapabilities:
    import svtypes

    provider = getattr(svtypes, "runtime_capabilities", None)
    if not callable(provider):
        raise SVXError(
            "SVX requires the SvTypes 1.x public runtime_capabilities() API"
        )
    raw = provider()
    try:
        capabilities = SvTypesCapabilities(
            package_major_version=int(_field(raw, "package_major_version")),
            schema_format_version=int(_field(raw, "schema_format_version")),
            binary_format_version=int(_field(raw, "binary_format_version")),
            object_envelope_version=int(_field(raw, "object_envelope_version")),
            generator_runtime_abi_version=int(
                _field(raw, "generator_runtime_abi_version")
            ),
            provided=frozenset(str(capability) for capability in _field(raw, "provided")),
        )
    except (TypeError, ValueError) as exc:
        raise SVXError(f"invalid SvTypes runtime capability descriptor: {exc}") from exc

    if capabilities.package_major_version != SVTYPES_PACKAGE_MAJOR_VERSION:
        raise SVXError(
            "SVX 1.x requires SvTypes major "
            f"{SVTYPES_PACKAGE_MAJOR_VERSION}, got {capabilities.package_major_version}"
        )
    required_versions = {
        "schema_format_version": SVTYPES_SCHEMA_FORMAT_VERSION,
        "binary_format_version": SVTYPES_BINARY_FORMAT_VERSION,
        "object_envelope_version": SVTYPES_OBJECT_ENVELOPE_VERSION,
        "generator_runtime_abi_version": SVTYPES_GENERATOR_RUNTIME_ABI_VERSION,
    }
    for field, expected in required_versions.items():
        received = getattr(capabilities, field)
        if received != expected:
            raise SVXError(
                f"SVX 1.x requires SvTypes {field} {expected}, got {received}"
            )
    missing = sorted(set(SVTYPES_REQUIRED_CAPABILITIES) - capabilities.provided)
    if missing:
        raise SVXError(
            "SvTypes runtime is missing required SVX capabilities: "
            + ", ".join(missing)
        )
    return capabilities


def _load_artifact_manifest(
    path: Path, capabilities: SvTypesCapabilities
) -> None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SVXError(f"cannot read SVX generated-artifact manifest {path}: {exc}") from exc
    if raw.get("schema_uri") != "https://svx.dev/schema/generated-artifacts/v1":
        raise SVXError(f"unsupported SVX generated-artifact manifest schema in {path}")
    if raw.get("generator_abi_version") != SVX_GENERATOR_ABI_VERSION:
        raise SVXError(
            "SVX generator/runtime ABI mismatch: "
            f"runtime expects {SVX_GENERATOR_ABI_VERSION}, artifact reports "
            f"{raw.get('generator_abi_version')!r}"
        )
    if raw.get("svx_runtime_abi_version") != SVX_RUNTIME_ABI_VERSION:
        raise SVXError(
            "SVX generated artifact/runtime ABI mismatch: "
            f"runtime expects {SVX_RUNTIME_ABI_VERSION}, artifact reports "
            f"{raw.get('svx_runtime_abi_version')!r}"
        )
    svtypes_requirement = raw.get("svtypes")
    if not isinstance(svtypes_requirement, Mapping):
        raise SVXError(f"generated artifact manifest has no SvTypes requirement: {path}")
    required_major = svtypes_requirement.get("required_package_major")
    if required_major != capabilities.package_major_version:
        raise SVXError(
            "generated artifact/SvTypes major mismatch: "
            f"artifact requires {required_major!r}, runtime reports "
            f"{capabilities.package_major_version}"
        )
    inheritance = raw.get("inheritance_manifest", {})
    version = inheritance.get("schema_version")
    if not isinstance(version, str) or version.split(".", 1)[0] != str(
        SVX_MANIFEST_SCHEMA_MAJOR
    ):
        raise SVXError(f"unsupported inheritance manifest version {version!r} in {path}")
    required = raw.get("required_runtime_capabilities")
    if not isinstance(required, list) or not all(isinstance(bit, str) for bit in required):
        raise SVXError(f"invalid required_runtime_capabilities in {path}")
    missing = sorted(set(required) - capabilities.provided)
    if missing:
        raise SVXError(
            f"generated artifacts require unavailable SvTypes capabilities: {', '.join(missing)}"
        )

    types = raw.get("types")
    if not isinstance(types, list):
        raise SVXError(f"generated artifact manifest has no type table: {path}")
    from .inheritance import (
        _call_record_class_name,
        _call_record_type_id,
        _codec_from_spec,
    )
    import svtypes

    type_ids: set[str] = set()
    type_specs: dict[str, Mapping] = {}
    for index, spec in enumerate(types):
        if not isinstance(spec, Mapping):
            raise SVXError(f"invalid generated type entry {index} in {path}")
        try:
            codec = _codec_from_spec(dict(spec))
            actual = svtypes.encoding_descriptor(codec).to_dict()
        except Exception as exc:
            raise SVXError(
                f"cannot resolve generated SvTypes entry {index} in {path}: {exc}"
            ) from exc
        if actual != spec.get("encoding_descriptor"):
            raise SVXError(
                "generated SvTypes encoding descriptor mismatch for "
                f"{spec.get('unified_type_name')!r}"
            )
        type_id = spec.get("unified_type_name")
        if not isinstance(type_id, str) or not type_id or type_id in type_ids:
            raise SVXError(f"invalid or duplicate generated type ID {type_id!r} in {path}")
        type_ids.add(type_id)
        type_specs[type_id] = spec

    def validate_fields(
        owner: str,
        kind: str,
        fields: object,
        allowed_directions: set[str] | None = None,
    ) -> list[Mapping]:
        if not isinstance(fields, list):
            raise SVXError(f"invalid {kind}_fields for {owner!r} in {path}")
        names: set[str] = set()
        for field in fields:
            if not isinstance(field, Mapping):
                raise SVXError(f"invalid {kind} field for {owner!r} in {path}")
            name = field.get("name")
            type_id = field.get("unified_type_name")
            if not isinstance(name, str) or not name or name in names:
                raise SVXError(f"invalid or duplicate {kind} field name for {owner!r}")
            if type_id not in type_ids:
                raise SVXError(
                    f"{owner!r} {kind} field {name!r} references unknown type {type_id!r}"
                )
            if allowed_directions is not None and field.get("direction") not in allowed_directions:
                raise SVXError(
                    f"{owner!r} {kind} field {name!r} has invalid direction "
                    f"{field.get('direction')!r}"
                )
            names.add(name)
        return fields

    def validate_record(owner: str, kind: str, fields: list[Mapping], record: object) -> None:
        if not fields:
            if record is not None:
                raise SVXError(f"void {kind} for {owner!r} declares a record")
            return
        if not isinstance(record, Mapping):
            raise SVXError(f"non-void {kind} for {owner!r} has no record")
        expected = _call_record_type_id(owner, kind)
        if record.get("unified_type_name") != expected:
            raise SVXError(
                f"generated {kind} record ID mismatch for {owner!r}: "
                f"expected {expected!r}, got {record.get('unified_type_name')!r}"
            )
        expected_class = _call_record_class_name(owner, kind)
        if record.get("sv_class") != expected_class:
            raise SVXError(
                f"generated {kind} record class mismatch for {owner!r}: "
                f"expected {expected_class!r}, got {record.get('sv_class')!r}"
            )
        schema_type = getattr(svtypes, "RecordSchema", None)
        if schema_type is None:
            raise SVXError("SvTypes runtime does not expose public RecordSchema")
        try:
            schema = schema_type(
                expected,
                tuple(
                    (
                        str(field["name"]),
                        _codec_from_spec(dict(type_specs[str(field["unified_type_name"])])),
                    )
                    for field in fields
                ),
                class_name=expected_class,
            )
            record_type = schema.build()
            descriptor = svtypes.encoding_descriptor(record_type).to_dict()
        except Exception as exc:
            raise SVXError(
                f"cannot reconstruct generated {kind} record for {owner!r}: {exc}"
            ) from exc
        if descriptor != record.get("encoding_descriptor"):
            raise SVXError(
                f"generated {kind} record encoding descriptor mismatch for {owner!r}"
            )

    callables = raw.get("callables")
    if not isinstance(callables, list):
        raise SVXError(f"generated artifact manifest has no callable table: {path}")
    callable_ids: set[str] = set()
    for entry in callables:
        if not isinstance(entry, Mapping):
            raise SVXError(f"invalid callable entry in {path}")
        method_id = entry.get("canonical_id")
        if not isinstance(method_id, str) or "#" not in method_id or method_id in callable_ids:
            raise SVXError(f"invalid or duplicate callable ID {method_id!r} in {path}")
        callable_ids.add(method_id)
        request_fields = validate_fields(
            method_id,
            "request",
            entry.get("request_fields"),
            {"input", "inout"},
        )
        response_fields = validate_fields(
            method_id,
            "response",
            entry.get("response_fields"),
            {"output", "inout", "return"},
        )
        for field in response_fields:
            if (field.get("name") == "result") != (field.get("direction") == "return"):
                raise SVXError(
                    f"{method_id!r} response reserves field 'result' for return direction"
                )
        validate_record(method_id, "request", request_fields, entry.get("request_record"))
        validate_record(method_id, "response", response_fields, entry.get("response_record"))

    constructors = raw.get("constructors")
    if not isinstance(constructors, list):
        raise SVXError(f"generated artifact manifest has no constructor table: {path}")
    constructor_ids: set[str] = set()
    for entry in constructors:
        if not isinstance(entry, Mapping):
            raise SVXError(f"invalid constructor entry in {path}")
        class_id = entry.get("canonical_class_id")
        if not isinstance(class_id, str) or class_id in constructor_ids:
            raise SVXError(f"invalid or duplicate constructor ID {class_id!r} in {path}")
        constructor_ids.add(class_id)
        request_fields = validate_fields(class_id, "request", entry.get("request_fields"))
        validate_record(class_id, "request", request_fields, entry.get("request_record"))

    root = path.parent.resolve()
    python_modules: list[tuple[str, Path]] = []
    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, list):
        raise SVXError(f"invalid artifacts list in {path}")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise SVXError(f"invalid artifact entry in {path}")
        relative = artifact.get("path")
        digest = artifact.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise SVXError(f"artifact path/hash is invalid in {path}")
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root):
            raise SVXError(f"artifact path escapes its manifest directory: {relative!r}")
        try:
            actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError as exc:
            raise SVXError(f"cannot read generated artifact {candidate}: {exc}") from exc
        if actual != digest:
            raise SVXError(f"generated artifact hash mismatch: {candidate}")
        if artifact.get("language") == "python":
            module = artifact.get("module")
            if not isinstance(module, str) or not module:
                raise SVXError(f"Python artifact is missing its module identity: {relative!r}")
            python_modules.append((module, candidate))

    import_roots: set[Path] = set()
    for module, candidate in python_modules:
        depth = len(module.split("."))
        import_root = candidate.parent
        parent_count = depth if candidate.name == "__init__.py" else depth - 1
        for _ in range(parent_count):
            import_root = import_root.parent
        import_roots.add(import_root)
    for import_root in sorted(import_roots, key=str):
        root_text = str(import_root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
    for module, _ in python_modules:
        importlib.import_module(module)


def _load_configured_artifacts(capabilities: SvTypesCapabilities) -> None:
    configured = os.environ.get("SVX_ARTIFACT_MANIFEST", "")
    for item in configured.split(os.pathsep):
        if item:
            _load_artifact_manifest(Path(item).expanduser().resolve(), capabilities)


def _native_initialize(
    native_abi_version: int, native_product_version: str | None = None
) -> None:
    """Prepare the Python-owned state while native initialization is pending."""

    global _state, _codec_session, _svtypes_capabilities
    if native_abi_version != SVX_RUNTIME_ABI_VERSION:
        raise SVXError(
            "SVX Python/native ABI mismatch: "
            f"Python expects {SVX_RUNTIME_ABI_VERSION}, native reports {native_abi_version}"
        )
    if native_product_version is not None and native_product_version != __version__:
        raise SVXError(
            "SVX Python/native product version mismatch: "
            f"Python is {__version__}, native is {native_product_version}"
        )
    if _state is RuntimeState.READY:
        return
    if _state is not RuntimeState.UNINITIALIZED:
        raise SVXError(f"SVX runtime cannot initialize from state {_state.value!r}")

    _state = RuntimeState.INITIALIZING
    try:
        capabilities = _read_svtypes_capabilities()
        import svtypes

        session_type = getattr(svtypes, "CodecSession", None)
        if session_type is None:
            raise SVXError("SVX requires the SvTypes 1.x public CodecSession API")
        session = session_type()
        _load_configured_artifacts(capabilities)
    except BaseException:
        if "session" in locals():
            close = getattr(session, "close", None)
            if callable(close):
                close()
        _codec_session = None
        _svtypes_capabilities = None
        _state = RuntimeState.UNINITIALIZED
        raise

    _svtypes_capabilities = capabilities
    _codec_session = session
    # Native code commits READY only after every configured declaration and
    # generated artifact has passed validation.


def _native_finish_initialize() -> None:
    global _state
    if _state is not RuntimeState.INITIALIZING:
        raise SVXError(
            f"SVX runtime cannot finish initialization from state {_state.value!r}"
        )
    _state = RuntimeState.READY


def _native_abort_initialize() -> None:
    """Roll back a failed initialization without creating a stopped session."""

    global _state, _codec_session, _svtypes_capabilities
    if _state is not RuntimeState.INITIALIZING:
        return
    if _codec_session is not None:
        close = getattr(_codec_session, "close", None)
        if callable(close):
            close()
    _codec_session = None
    _svtypes_capabilities = None
    _state = RuntimeState.UNINITIALIZED


def _native_shutdown() -> None:
    """Release Python registries and the SvTypes session deterministically."""

    global _state, _codec_session, _svtypes_capabilities
    if _state in {RuntimeState.UNINITIALIZED, RuntimeState.STOPPED}:
        _state = RuntimeState.STOPPED
        return
    if _state is RuntimeState.SHUTTING_DOWN:
        return

    _state = RuntimeState.SHUTTING_DOWN
    try:
        from . import _registry
        from . import inheritance

        inheritance._shutdown_python_state()
        _registry.clear()
        if _codec_session is not None:
            close = getattr(_codec_session, "close", None)
            if callable(close):
                close()
    finally:
        _codec_session = None
        _svtypes_capabilities = None
        _state = RuntimeState.STOPPED


def state() -> RuntimeState:
    return _state


def require_ready(operation: str) -> None:
    if _state is not RuntimeState.READY:
        raise SVXError(
            f"{operation} requires an initialized SVX runtime; current state is {_state.value!r}"
        )


def codec_session() -> Any:
    require_ready("SvTypes codec operation")
    return _codec_session


def svtypes_capabilities() -> SvTypesCapabilities:
    require_ready("SvTypes capability query")
    assert _svtypes_capabilities is not None
    return _svtypes_capabilities
