"""Manifest, mirrors, and SvTypes-backed cross-language inheritance dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, fields as dataclass_fields, replace
from contextvars import ContextVar
import ast
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path, PurePosixPath
from pprint import pformat
import re
import tempfile
from typing import Any, Callable, Iterable, Mapping

from .errors import SVXCancellationError, SVXInheritanceError, SVXRemoteError
from ._constructor_continuation import ConstructorContinuations
from ._inheritance_diagnostics import inheritance_boundary
from ._svtypes_contract import SVTYPES_REQUIRED_CAPABILITIES, require_type_spec_api
from .discovery_provenance import DiscoveryProvenance, discovery_marker, validate_discovery_provenance


SCHEMA_URI = "https://svx.dev/schema/inheritance-manifest/v2"
SCHEMA_VERSION = "2.0.0"
GENERATOR_ABI_VERSION = 2
REQUIRED_RUNTIME_CAPABILITIES = SVTYPES_REQUIRED_CAPABILITIES
EXTERNAL_FIELD_STORAGE_CAPABILITY = "svtypes.external-field-storage.v1"
MAX_CALL_PAYLOAD_BYTES = 16 * 1024 * 1024
_PYTHON_BASE_METHOD_PREFIX = "svx-python-base:"
_PYTHON_STATIC_METHOD_PREFIX = "svx-python-static:"
_PYTHON_CALLBACK_METHOD_PREFIX = "svx-python-callback:"
_PYTHON_ROOT_INIT_PREFIX = "svx-python-root-init:"
_PYTHON_ROOT_ALLOC_PREFIX = "svx-python-root-allocate:"
_PYTHON_PORTION_INIT_PREFIX = "svx-python-portion-init:"
_PYTHON_RECEIVER_RESERVE_PREFIX = "svx-python-receiver-reserve:"
_PYTHON_RECEIVER_EXPECT_PREFIX = "svx-python-receiver-expect:"
_SV_CONSTRUCTOR_ARGUMENTS_PREFIX = "svx-sv-constructor-arguments:"
_NATURAL_CONSTRUCTOR_PREFIX = "svx-natural-constructor:"
# This is private SVX record framing, not a user-visible Python parameter.
# Do not use ``result``: SvTypes' generated SV ``svtypes_sprint`` uses that
# name as a local variable, and a RemoteRef field would shadow it.
_RETURN_FIELD_NAME = "svx_return_value"
LEGACY_SCHEMA_URI = "https://svx.dev/schema/inheritance-manifest/v1"
_LEGACY_TYPES = {
    "bit": {"svtypes": "svtypes.Bit(1)", "sv": "bit", "sv_packer": "bits_packer#(bit)"},
    "int": {"svtypes": "svtypes.Int()", "sv": "int", "sv_packer": "int_packer"},
    "longint": {"svtypes": "svtypes.LongInt()", "sv": "longint", "sv_packer": "longint_packer"},
    "string": {"svtypes": "svtypes.String()", "sv": "string", "sv_packer": "string_packer"},
    "real": {"svtypes": "svtypes.Real()", "sv": "real", "sv_packer": "real_packer"},
}
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CANONICAL_ID = re.compile(r"^(sv|py)://[A-Za-z_][A-Za-z0-9_./]*$")
_SCHEMA_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
@dataclass(frozen=True)
class TypeBinding:
    """One immutable public SvTypes declaration and generated SV adapter."""

    unified_type_name: str
    sv: str
    sv_packer: str
    encoding_descriptor: tuple[tuple[str, Any], ...]
    # New manifests retain only SvTypes' canonical, JSON-compatible type
    # identity. Legacy factory references remain readable for old manifests
    # and descriptor-backed fields, but are never emitted for method types.
    svtypes_identity_json: str | None = None
    python_module: str | None = None
    python_symbol: str | None = None
    python_args: tuple[Any, ...] = ()
    python_kwargs: tuple[tuple[str, Any], ...] = ()

    def runtime_spec(self) -> dict[str, Any]:
        result = {
            "unified_type_name": self.unified_type_name,
            "encoding_descriptor": dict(self.encoding_descriptor),
        }
        if self.svtypes_identity_json is not None:
            result["svtypes"] = json.loads(self.svtypes_identity_json)
        else:
            assert self.python_module is not None and self.python_symbol is not None
            result["python"] = {
                "module": self.python_module,
                "symbol": self.python_symbol,
                "args": list(self.python_args),
                "kwargs": dict(self.python_kwargs),
            }
        return result


@dataclass(frozen=True)
class VifOperation:
    """One generated member operation exposed by a virtual-interface view."""

    method: Method
    operation: str
    sv_member_name: str


@dataclass(frozen=True)
class HandleBinding:
    """The typed SV endpoint behind one SvTypes ``RemoteRef`` value.

    ``type_binding`` remains the sole encoded call contract. This description
    exists only at the generated SV boundary, where a remote-reference record
    field is converted to an actual SV class or virtual-interface handle.
    """

    kind: str
    target_type_name: str
    sv_type: str
    operations: tuple[VifOperation, ...] = ()
    collection_binding: TypeBinding | None = None


@dataclass(frozen=True)
class Parameter:
    name: str
    type_binding: TypeBinding
    direction: str
    handle: HandleBinding | None = None


@dataclass(frozen=True)
class Method:
    canonical_id: str
    name: str
    parameters: tuple[Parameter, ...]
    return_type: TypeBinding | None
    return_handle: HandleBinding | None
    timing: str
    virtual: bool
    pure_virtual: bool
    is_static: bool


@dataclass(frozen=True)
class Constructor:
    initiator: str
    parameters: tuple[Parameter, ...]


@dataclass(frozen=True)
class Field:
    """One directly declared, schema-backed instance field."""

    name: str
    type_binding: TypeBinding
    handle: HandleBinding | None = None


@dataclass(frozen=True)
class SpecializationArgument:
    """One closed SV parameterized-class argument."""

    kind: str
    type_binding: TypeBinding | None = None
    sv_type: str | None = None
    value: Any = None


@dataclass(frozen=True)
class Specialization:
    """A normalized, concrete SV class specialization."""

    arguments: tuple[SpecializationArgument, ...]


@dataclass(frozen=True)
class ForeignClass:
    canonical_id: str
    language: str
    symbol: str
    methods: tuple[Method, ...]
    constructor: Constructor | None
    specialization: Specialization | None = None
    fields: tuple[Field, ...] = ()
    # Root-to-direct-parent context for this generation target.  Its members
    # are descriptions only; they never independently request code emission.
    base_lineage: tuple["ForeignClass", ...] = ()

    @property
    def name(self) -> str:
        return self.symbol.split("::")[-1].split(".")[-1]

    @property
    def generated_name(self) -> str:
        """Public generated types always preserve the source simple name.

        Multiple closed specializations of one source class cannot occupy the
        same public package/module in one artifact set.  Name validation
        rejects that request instead of introducing a hash suffix.
        """

        return self.name


@dataclass(frozen=True)
class Manifest:
    schema_uri: str
    schema_version: str
    generator_abi_version: int
    required_runtime_capabilities: tuple[str, ...]
    classes: tuple[ForeignClass, ...]
    discovery_provenance: DiscoveryProvenance | None = None


@dataclass(frozen=True)
class ProjectionStep:
    """One generated cross-language class portion for a target lineage."""

    kind: str
    source_class_id: str
    generated_name: str
    extends_class_id: str


@dataclass(frozen=True)
class ProjectionPlan:
    """The minimal generated portions required for one top-level target."""

    target_class_id: str
    lineage: tuple[ForeignClass, ...]
    steps: tuple[ProjectionStep, ...]


@dataclass(frozen=True)
class _PythonRootConstructionPlan:
    root: ForeignClass
    ancestors: tuple[ForeignClass, ...]
    python_portions: tuple[ForeignClass, ...]
    preceding_python: ForeignClass | None


@dataclass(frozen=True)
class _SVRootConstructionPlan:
    root: ForeignClass
    # Earlier ordinary SV ancestors are context, not separate bridge owners.
    bridge_root: ForeignClass
    ancestors: tuple[ForeignClass, ...]
    first_python: ForeignClass | None
    python_portions: tuple[ForeignClass, ...]
    preceding_python: ForeignClass | None


def _error(where: str, message: str) -> SVXInheritanceError:
    return SVXInheritanceError(f"inheritance manifest {where}: {message}")


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(where, "must be an object")
    return value


def _reject_unknown(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error(where, f"contains unsupported fields: {', '.join(unknown)}")


def _required_string(value: dict[str, Any], key: str, where: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise _error(where, f"{key!r} must be a non-empty string")
    return result


def _identifier(value: str, where: str) -> str:
    if not _IDENT.fullmatch(value):
        raise _error(where, f"{value!r} is not a valid identifier")
    return value


def _codec_from_spec(spec: dict[str, Any]):
    """Construct a codec from a non-executable public declaration reference."""

    identity = spec.get("svtypes")
    if identity is not None:
        try:
            import svtypes

            require_type_spec_api(svtypes)
            annotation = svtypes.type_spec_from_identity(identity, location="SVX manifest type")
            return svtypes.materialize_type_spec(annotation, location="SVX manifest type")
        except Exception as error:
            raise SVXInheritanceError(
                f"SvTypes declaration identity cannot be materialized: {error}"
            ) from error

    python = spec.get("python")
    if not isinstance(python, dict):
        raise SVXInheritanceError("SvTypes declaration is missing its Python reference")
    module_name = python.get("module")
    symbol = python.get("symbol")
    args = python.get("args", [])
    kwargs = python.get("kwargs", {})
    if not isinstance(module_name, str) or not isinstance(symbol, str):
        raise SVXInheritanceError("invalid SvTypes Python declaration reference")
    module = importlib.import_module(module_name)
    factory = getattr(module, symbol, None)
    if factory is None or not callable(factory):
        raise SVXInheritanceError(
            f"SvTypes declaration factory {module_name}:{symbol} is unavailable"
        )
    codec = factory(*args, **kwargs)
    if not callable(getattr(codec, "sv_decl", None)):
        raise SVXInheritanceError(
            f"SvTypes declaration {module_name}:{symbol} does not provide an SV declaration"
        )
    return codec


def _legacy_expression_spec(expression: str) -> dict[str, Any]:
    module_name = "svtypes"
    source = expression
    if ":" in expression:
        module_name, source = expression.split(":", 1)
    try:
        node = ast.parse(source, mode="eval").body
    except SyntaxError as error:
        raise SVXInheritanceError(
            f"cannot migrate invalid SvTypes expression {expression!r}: {error.msg}"
        ) from error
    if not isinstance(node, ast.Call) or node.keywords and any(
        keyword.arg is None for keyword in node.keywords
    ):
        raise SVXInheritanceError(
            f"cannot migrate non-constructor SvTypes expression {expression!r}"
        )
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        if node.func.value.id != "svtypes":
            raise SVXInheritanceError(
                f"cannot migrate foreign expression root in {expression!r}"
            )
        module_name = "svtypes"
        symbol = node.func.attr
    elif isinstance(node.func, ast.Name) and module_name != "svtypes":
        symbol = node.func.id
    else:
        raise SVXInheritanceError(
            f"cannot migrate unsupported SvTypes expression {expression!r}"
        )
    try:
        args = [ast.literal_eval(value) for value in node.args]
        kwargs = {keyword.arg: ast.literal_eval(keyword.value) for keyword in node.keywords}
    except (TypeError, ValueError) as error:
        raise SVXInheritanceError(
            f"SvTypes migration accepts only JSON-like literal arguments: {expression!r}"
        ) from error
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, symbol)
        if module_name == "svtypes" and symbol in {"Bit", "Logic", "Reg"}:
            if not args:
                raise TypeError(f"{symbol} requires a width")
            annotation = factory[args[0]]
            codec = annotation(**kwargs)
        elif module_name == "svtypes" and symbol in {"RemoteRef", "Object"}:
            if not args:
                raise TypeError(f"{symbol} requires a target")
            annotation = factory[args[0]]
            codec = annotation(**kwargs)
        elif module_name == "svtypes" and symbol in {"Array", "DynArray", "Queue", "AssocArray"}:
            raise TypeError("legacy collection declarations require manual migration to bracket syntax")
        else:
            annotation = factory
            codec = factory(*args, **kwargs)
        import svtypes

        return {
            "svtypes": svtypes.type_spec_identity(annotation, location="legacy manifest migration"),
        }
    except Exception as error:
        raise SVXInheritanceError(
            f"cannot migrate SvTypes expression {expression!r}: {error}"
        ) from error


def _legacy_python_spec(value: dict[str, Any], where: str) -> dict[str, Any]:
    """Turn a legacy factory reference into one SvTypes public type identity."""

    module_name = value.get("module")
    symbol = value.get("symbol")
    args = value.get("args", [])
    kwargs = value.get("kwargs", {})
    if not isinstance(module_name, str) or not isinstance(symbol, str):
        raise _error(where, "legacy Python reference requires string module and symbol")
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        raise _error(where, "legacy Python reference requires list args and object kwargs")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, symbol)
        if module_name == "svtypes" and symbol in {"Bit", "Logic", "Reg"}:
            if kwargs or not args:
                raise TypeError(f"{symbol} migration requires exactly one positional shape")
            annotation = factory[tuple(args) if len(args) > 1 else args[0]]
        elif module_name == "svtypes" and symbol in {"RemoteRef", "Object"}:
            if kwargs or len(args) != 1:
                raise TypeError(f"{symbol} migration requires exactly one target argument")
            annotation = factory[args[0]]
        elif args or kwargs:
            raise TypeError(
                "legacy factory references with arguments require an explicit bracket-style SvTypes declaration"
            )
        else:
            annotation = factory
        import svtypes

        return {
            "svtypes": svtypes.type_spec_identity(
                annotation, location="legacy manifest migration"
            ),
        }
    except Exception as error:
        raise SVXInheritanceError(
            f"cannot migrate legacy Python declaration {module_name}:{symbol}: {error}"
        ) from error


def _migrate_type_binding(value: Any, where: str) -> Any:
    if value == "void":
        return value
    if isinstance(value, str) and value in _LEGACY_TYPES:
        value = _LEGACY_TYPES[value]
    if not isinstance(value, dict):
        return value
    if "svtypes" in value:
        expression = value.get("svtypes")
        if not isinstance(expression, str):
            return value
        spec = _legacy_expression_spec(expression)
    elif "python" in value:
        python = value.get("python")
        if not isinstance(python, dict):
            raise _error(where, "legacy Python declaration must be an object")
        spec = _legacy_python_spec(python, where)
    else:
        return value
    codec = _codec_from_spec(spec)
    import svtypes

    return {
        "unified_type_name": svtypes.unified_type_name(codec),
        "svtypes": spec["svtypes"],
        "sv": value.get("sv"),
        "sv_packer": value.get("sv_packer"),
        "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict(),
    }


def _type_binding(value: Any, where: str, *, allow_void: bool) -> TypeBinding | None:
    if allow_void and value == "void":
        return None
    raw = _object(value, where)
    _reject_unknown(
        raw,
        {"unified_type_name", "svtypes", "python", "sv", "sv_packer", "encoding_descriptor"},
        where,
    )
    identity = raw.get("svtypes")
    python = raw.get("python")
    if (identity is None) == (python is None):
        raise _error(where, "must contain exactly one of 'svtypes' or legacy 'python'")
    descriptor = _object(raw.get("encoding_descriptor"), f"{where}.encoding_descriptor")
    _reject_unknown(
        descriptor,
        {"unified_type_name", "encoding_fingerprint", "binary_format_version"},
        f"{where}.encoding_descriptor",
    )
    common = {
        "unified_type_name": _required_string(raw, "unified_type_name", where),
        "sv": _required_string(raw, "sv", where),
        "sv_packer": _required_string(raw, "sv_packer", where),
        "encoding_descriptor": tuple(sorted(descriptor.items())),
    }
    if identity is not None:
        if not isinstance(identity, dict):
            raise _error(f"{where}.svtypes", "must be a canonical SvTypes identity object")
        try:
            identity_json = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise _error(f"{where}.svtypes", "must be JSON-compatible") from error
        binding = TypeBinding(**common, svtypes_identity_json=identity_json)
    else:
        assert isinstance(python, dict)
        python = _object(python, f"{where}.python")
        _reject_unknown(python, {"module", "symbol", "args", "kwargs"}, f"{where}.python")
        args = python.get("args", [])
        kwargs = python.get("kwargs", {})
        if not isinstance(args, list):
            raise _error(f"{where}.python.args", "must be a JSON list")
        if not isinstance(kwargs, dict) or any(not isinstance(key, str) for key in kwargs):
            raise _error(f"{where}.python.kwargs", "must be a JSON object with string keys")
        binding = TypeBinding(
            **common,
            python_module=_required_string(python, "module", f"{where}.python"),
            python_symbol=_identifier(
                _required_string(python, "symbol", f"{where}.python"),
                f"{where}.python.symbol",
            ),
            python_args=tuple(args),
            python_kwargs=tuple(sorted(kwargs.items())),
        )
    for field, content, grammar in (
        ("unified_type_name", binding.unified_type_name, r"[^\s]+"),
        # SvTypes collections use ordinary SV unpacked dimensions such as
        # ``int []`` and ``int [$]``.  Keep the grammar deliberately narrow
        # while permitting those generated declaration forms.
        ("sv", binding.sv, r"[$A-Za-z_][A-Za-z0-9_:$#() ,\[\]]*"),
        ("sv_packer", binding.sv_packer, r"[A-Za-z_][A-Za-z0-9_:.$#() ,\[\]]*"),
    ):
        if not re.fullmatch(grammar, content):
            raise _error(f"{where}.{field}", "contains unsupported source characters")
    if binding.python_module is not None and not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_.]*", binding.python_module
    ):
        raise _error(f"{where}.python.module", "contains unsupported source characters")
    try:
        codec = _codec_from_spec(binding.runtime_spec())
        import svtypes

        actual_type_id = svtypes.unified_type_name(codec)
        actual_descriptor = svtypes.encoding_descriptor(codec).to_dict()
    except Exception as error:
        raise _error(where, f"cannot resolve public SvTypes declaration: {error}") from error
    if actual_type_id != binding.unified_type_name:
        raise _error(
            f"{where}.unified_type_name",
            f"declares {binding.unified_type_name!r}, resolved {actual_type_id!r}",
        )
    if actual_descriptor != dict(binding.encoding_descriptor):
        raise _error(f"{where}.encoding_descriptor", "does not match the resolved SvTypes codec")
    return binding


def _remote_ref_target(binding: TypeBinding, where: str) -> str:
    """Return the SvTypes RemoteRef target declared by ``binding``."""

    try:
        import svtypes

        codec = _codec_from_spec(binding.runtime_spec())
        remote_ref = getattr(svtypes, "RemoteRef", None)
        while isinstance(codec, (svtypes.Array, svtypes.DynArray, svtypes.AssocArray)):
            codec = (codec.value_codec if isinstance(codec, svtypes.AssocArray) else
                     svtypes.FieldDescriptor(codec).resolve_path(svtypes.FieldPath().index(0)).codec)
        if remote_ref is None or not isinstance(codec, remote_ref):
            raise TypeError("is not svtypes.RemoteRef[TARGET]")
        return codec.target_type_name
    except Exception as error:
        raise _error(where, f"must use a concrete SvTypes RemoteRef type: {error}") from error


def _handle_binding(value: Any, binding: TypeBinding, where: str) -> HandleBinding:
    """Parse typed foreign-handle metadata without changing its wire codec."""

    raw = _object(value, where)
    _reject_unknown(raw, {"kind", "target_type_name", "sv_type", "operations"}, where)
    kind = _required_string(raw, "kind", where)
    if kind not in {"sv_class", "virtual_interface"}:
        raise _error(f"{where}.kind", "must be sv_class or virtual_interface")
    target_type_name = _required_string(raw, "target_type_name", where)
    expected_target = _remote_ref_target(binding, f"{where}.type")
    if target_type_name != expected_target:
        raise _error(
            f"{where}.target_type_name",
            f"must match the SvTypes RemoteRef target {expected_target!r}",
        )
    if kind == "sv_class" and not target_type_name.startswith("sv://"):
        raise _error(f"{where}.target_type_name", "must use an sv:// target for an SV class")
    if kind == "virtual_interface" and not target_type_name.startswith("sv-vif://"):
        raise _error(
            f"{where}.target_type_name",
            "must use an sv-vif:// target for a virtual interface",
        )
    sv_type = _required_string(raw, "sv_type", where)
    if kind == "virtual_interface":
        valid = re.fullmatch(r"virtual [A-Za-z_$][A-Za-z0-9_$:.#() ,\[\]]*", sv_type)
    else:
        valid = re.fullmatch(r"[$A-Za-z_][A-Za-z0-9_:$#() ,.\[\]]*", sv_type)
    if not valid:
        raise _error(f"{where}.sv_type", "contains unsupported SystemVerilog type characters")
    raw_operations = raw.get("operations", [])
    if not isinstance(raw_operations, list):
        raise _error(f"{where}.operations", "must be a list")
    if kind != "virtual_interface" and raw_operations:
        raise _error(f"{where}.operations", "is valid only for virtual_interface handles")
    operations = tuple(
        _parse_vif_operation(item, target_type_name, f"{where}.operations[{index}]")
        for index, item in enumerate(raw_operations)
    )
    operation_names = [operation.method.name for operation in operations]
    if len(operation_names) != len(set(operation_names)):
        raise _error(f"{where}.operations", "contains duplicate generated operation names")
    import svtypes
    codec = _codec_from_spec(binding.runtime_spec())
    collection_binding = binding if isinstance(codec, (svtypes.Array, svtypes.DynArray, svtypes.AssocArray)) else None
    return HandleBinding(kind, target_type_name, sv_type, operations, collection_binding)


def _parse_parameter(value: Any, where: str) -> Parameter:
    raw = _object(value, where)
    _reject_unknown(raw, {"name", "type", "direction", "handle"}, where)
    name = _identifier(_required_string(raw, "name", where), f"{where}.name")
    type_binding = _type_binding(raw.get("type"), f"{where}.type", allow_void=False)
    direction = raw.get("direction", "input")
    if direction in {"ref", "const ref"}:
        raise _error(
            f"{where}.direction",
            "ref and const ref are not supported across an SVX inheritance boundary; use input, output, or inout",
        )
    if direction not in {"input", "output", "inout"}:
        raise _error(f"{where}.direction", "must be input, output, or inout")
    assert type_binding is not None
    handle_raw = raw.get("handle")
    handle = (
        _handle_binding(handle_raw, type_binding, f"{where}.handle")
        if handle_raw is not None
        else None
    )
    return Parameter(
        name=name,
        type_binding=type_binding,
        direction=direction,
        handle=handle,
    )


def _parse_field(value: Any, where: str) -> Field:
    raw = _object(value, where)
    _reject_unknown(raw, {"name", "type", "handle"}, where)
    name = _identifier(_required_string(raw, "name", where), f"{where}.name")
    type_binding = _type_binding(raw.get("type"), f"{where}.type", allow_void=False)
    assert type_binding is not None
    handle = _handle_binding(raw["handle"], type_binding, f"{where}.handle") if "handle" in raw else None
    return Field(name, type_binding, handle)


def _json_literal(value: Any, where: str) -> Any:
    """Accept normalized scalar specialization values, never source expressions."""

    if isinstance(value, (bool, int, float, str)):
        return value
    raise _error(where, "must be a normalized JSON scalar literal")


def _parse_specialization(value: Any, where: str, language: str) -> Specialization:
    if language != "sv":
        raise _error(where, "is valid only for SystemVerilog classes")
    raw = _object(value, where)
    _reject_unknown(raw, {"arguments"}, where)
    arguments_raw = raw.get("arguments")
    if not isinstance(arguments_raw, list) or not arguments_raw:
        raise _error(f"{where}.arguments", "must be a non-empty list")
    arguments: list[SpecializationArgument] = []
    for index, item in enumerate(arguments_raw):
        argument_where = f"{where}.arguments[{index}]"
        argument = _object(item, argument_where)
        kind = _required_string(argument, "kind", argument_where)
        if kind == "type":
            _reject_unknown(argument, {"kind", "type"}, argument_where)
            arguments.append(
                SpecializationArgument(
                    kind="type",
                    type_binding=_type_binding(argument.get("type"), f"{argument_where}.type", allow_void=False),
                )
            )
        elif kind == "value":
            _reject_unknown(argument, {"kind", "sv_type", "value"}, argument_where)
            sv_type = _required_string(argument, "sv_type", argument_where)
            if not re.fullmatch(r"[$A-Za-z_][A-Za-z0-9_:$ ]*", sv_type):
                raise _error(f"{argument_where}.sv_type", "contains unsupported source characters")
            arguments.append(
                SpecializationArgument(
                    kind="value",
                    sv_type=sv_type,
                    value=_json_literal(argument.get("value"), f"{argument_where}.value"),
                )
            )
        else:
            raise _error(f"{argument_where}.kind", "must be type or value")
    return Specialization(tuple(arguments))


def _specialization_dict(specialization: Specialization) -> dict[str, Any]:
    arguments: list[dict[str, Any]] = []
    for argument in specialization.arguments:
        if argument.kind == "type":
            assert argument.type_binding is not None
            arguments.append({"kind": "type", "type": argument.type_binding.runtime_spec() | {
                "sv": argument.type_binding.sv,
                "sv_packer": argument.type_binding.sv_packer,
            }})
        else:
            arguments.append(
                {"kind": "value", "sv_type": argument.sv_type, "value": argument.value}
            )
    return {"arguments": arguments}


def _sv_specialization_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1'b1" if value else "1'b0"
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


def _sv_class_reference(cls: ForeignClass) -> str:
    """Render the source class type, including only closed manifest arguments."""

    if cls.specialization is None:
        # Generated mirror classes deliberately retain the source simple name
        # in a different package.  Always qualify the source base so
        # ``class A extends pkg::A`` cannot resolve recursively to itself.
        return cls.symbol
    arguments: list[str] = []
    for argument in cls.specialization.arguments:
        if argument.kind == "type":
            assert argument.type_binding is not None
            arguments.append(argument.type_binding.sv)
        else:
            arguments.append(_sv_specialization_value(argument.value))
    return f"{cls.symbol}#({', '.join(arguments)})"


def _parse_method(value: Any, cls_id: str, where: str) -> Method:
    raw = _object(value, where)
    _reject_unknown(
        raw,
        {"canonical_id", "name", "parameters", "return_type", "return_handle", "timing", "virtual", "pure_virtual", "static"},
        where,
    )
    name = _identifier(_required_string(raw, "name", where), f"{where}.name")
    canonical_id = _required_string(raw, "canonical_id", where)
    expected_id = f"{cls_id}#{name}"
    if canonical_id != expected_id:
        raise _error(f"{where}.canonical_id", f"must be {expected_id!r}")

    raw_parameters = raw.get("parameters", [])
    if not isinstance(raw_parameters, list):
        raise _error(f"{where}.parameters", "must be a list")
    parameters = tuple(_parse_parameter(item, f"{where}.parameters[{index}]") for index, item in enumerate(raw_parameters))
    parameter_names = [parameter.name for parameter in parameters]
    if len(parameter_names) != len(set(parameter_names)):
        raise _error(f"{where}.parameters", "contains duplicate parameter names")

    return_type = _type_binding(raw.get("return_type"), f"{where}.return_type", allow_void=True)
    return_handle_raw = raw.get("return_handle")
    if return_handle_raw is not None and return_type is None:
        raise _error(f"{where}.return_handle", "requires a non-void return_type")
    return_handle = (
        _handle_binding(return_handle_raw, return_type, f"{where}.return_handle")
        if return_handle_raw is not None and return_type is not None
        else None
    )
    timing = _required_string(raw, "timing", where)
    if timing not in {"function", "task"}:
        raise _error(f"{where}.timing", "must be 'function' or 'task'")
    if timing == "task" and return_type is not None:
        raise _error(where, "task methods must have return_type 'void'")

    virtual = raw.get("virtual")
    pure_virtual = raw.get("pure_virtual", False)
    is_static = raw.get("static", False)
    if not isinstance(virtual, bool):
        raise _error(f"{where}.virtual", "must be a boolean")
    if not isinstance(pure_virtual, bool):
        raise _error(f"{where}.pure_virtual", "must be a boolean")
    if not isinstance(is_static, bool):
        raise _error(f"{where}.static", "must be a boolean")
    if pure_virtual and not virtual:
        raise _error(where, "pure_virtual methods must also be virtual")
    if is_static and virtual:
        raise _error(where, "static methods cannot be virtual across an SVX inheritance boundary")
    return Method(canonical_id, name, parameters, return_type, return_handle, timing, virtual, pure_virtual, is_static)


def _parse_vif_operation(value: Any, target_type_name: str, where: str) -> VifOperation:
    raw = _object(value, where)
    _reject_unknown(raw, {"operation", "member", "method"}, where)
    operation = _required_string(raw, "operation", where)
    if operation not in {"task", "function", "signal_read", "signal_write"}:
        raise _error(
            f"{where}.operation",
            "must be task, function, signal_read, or signal_write",
        )
    member = _identifier(_required_string(raw, "member", where), f"{where}.member")
    method_raw = _object(raw.get("method"), f"{where}.method")
    # VIF operations are generated private adapters, never virtual members of
    # a user inheritance class. Keep the method parser as the single source of
    # record-direction validation.
    method_data = dict(method_raw)
    method_data.setdefault("virtual", False)
    method_data.setdefault("pure_virtual", False)
    method = _parse_method(method_data, target_type_name, f"{where}.method")
    if method.is_static:
        raise _error(f"{where}.method.static", "is not valid for a virtual-interface operation")
    if operation in {"task", "signal_write"} and method.return_type is not None:
        raise _error(f"{where}.method.return_type", "must be void for this virtual-interface operation")
    if operation == "signal_read" and method.return_type is None:
        raise _error(f"{where}.method.return_type", "must be non-void for a signal read")
    return VifOperation(method, operation, member)


def _parse_constructor(value: Any, where: str) -> Constructor:
    raw = _object(value, where)
    _reject_unknown(raw, {"initiator", "parameters"}, where)
    initiator = _required_string(raw, "initiator", where)
    if initiator not in {"python", "sv"}:
        raise _error(f"{where}.initiator", "must be 'python' or 'sv'")
    raw_parameters = raw.get("parameters", [])
    if not isinstance(raw_parameters, list):
        raise _error(f"{where}.parameters", "must be a list")
    parameters = tuple(
        _parse_parameter(item, f"{where}.parameters[{index}]")
        for index, item in enumerate(raw_parameters)
    )
    if any(parameter.direction != "input" for parameter in parameters):
        raise _error(where, "constructor parameters must use input direction")
    names = [parameter.name for parameter in parameters]
    if len(names) != len(set(names)):
        raise _error(f"{where}.parameters", "contains duplicate parameter names")
    return Constructor(initiator, parameters)


def _validate_symbol(language: str, symbol: str, where: str) -> None:
    separator = "::" if language == "sv" else "."
    parts = symbol.split(separator)
    if len(parts) < 2 or any(not _IDENT.fullmatch(part) for part in parts):
        expected = "SV package::Class" if language == "sv" else "Python module.Class"
        raise _error(where, f"must be a {expected} symbol")


def _parse_class(value: Any, where: str, *, lineage_member: bool = False) -> ForeignClass:
    raw = _object(value, where)
    allowed = {
        "canonical_id",
        "language",
        "symbol",
        "methods",
        "constructor",
        "specialization",
        "fields",
    }
    if not lineage_member:
        allowed.add("base_lineage")
    _reject_unknown(raw, allowed, where)
    canonical_id = _required_string(raw, "canonical_id", where)
    match = _CANONICAL_ID.fullmatch(canonical_id)
    if match is None:
        raise _error(f"{where}.canonical_id", "must use a sv:// or py:// canonical ID")
    language = _required_string(raw, "language", where)
    if language not in {"sv", "python"}:
        raise _error(f"{where}.language", "must be 'sv' or 'python'")
    if match.group(1) != ("sv" if language == "sv" else "py"):
        raise _error(f"{where}.canonical_id", "scheme must match language")
    symbol = _required_string(raw, "symbol", where)
    _validate_symbol(language, symbol, f"{where}.symbol")
    specialization_raw = raw.get("specialization")
    specialization = (
        _parse_specialization(specialization_raw, f"{where}.specialization", language)
        if specialization_raw is not None
        else None
    )

    raw_methods = raw.get("methods", [])
    if not isinstance(raw_methods, list):
        raise _error(f"{where}.methods", "must be a list")
    methods = tuple(_parse_method(item, canonical_id, f"{where}.methods[{index}]") for index, item in enumerate(raw_methods))
    method_names = [method.name for method in methods]
    if len(method_names) != len(set(method_names)):
        raise _error(f"{where}.methods", "method overloads are not supported; names must be unique")
    raw_fields = raw.get("fields", [])
    if not isinstance(raw_fields, list):
        raise _error(f"{where}.fields", "must be a list")
    fields = tuple(_parse_field(item, f"{where}.fields[{index}]") for index, item in enumerate(raw_fields))
    field_names = [field.name for field in fields]
    if len(field_names) != len(set(field_names)):
        raise _error(f"{where}.fields", "contains duplicate field names")
    if set(field_names) & set(method_names):
        raise _error(f"{where}.fields", "field names must not collide with method names")
    constructor_raw = raw.get("constructor")
    constructor = _parse_constructor(constructor_raw, f"{where}.constructor") if constructor_raw is not None else None
    raw_lineage = raw.get("base_lineage", [])
    if not isinstance(raw_lineage, list):
        raise _error(f"{where}.base_lineage", "must be a list")
    if lineage_member and raw_lineage:
        raise _error(f"{where}.base_lineage", "may not nest inside a lineage member")
    base_lineage = tuple(
        _parse_class(item, f"{where}.base_lineage[{index}]", lineage_member=True)
        for index, item in enumerate(raw_lineage)
    )
    lineage_ids = [item.canonical_id for item in base_lineage]
    if canonical_id in lineage_ids:
        raise _error(f"{where}.base_lineage", "must not contain the target class itself")
    if len(lineage_ids) != len(set(lineage_ids)):
        raise _error(f"{where}.base_lineage", "contains duplicate canonical class IDs")
    return ForeignClass(
        canonical_id,
        language,
        symbol,
        methods,
        constructor,
        specialization,
        fields,
        base_lineage,
    )


def parse_manifest(data: Any, *, source_path: Path | None = None) -> Manifest:
    raw = _object(data, "root")
    _reject_unknown(
        raw,
        {
            "schema_uri",
            "schema_version",
            "generator_abi_version",
            "required_runtime_capabilities",
            "classes",
            "discovery_provenance",
        },
        "root",
    )
    validate_discovery_provenance(raw, source_path)
    provenance = discovery_marker(raw.get('discovery_provenance'))
    schema_uri = _required_string(raw, "schema_uri", "root")
    if schema_uri != SCHEMA_URI:
        raise _error("root.schema_uri", f"must be {SCHEMA_URI!r}")
    schema_version = _required_string(raw, "schema_version", "root")
    if not _SCHEMA_VERSION.fullmatch(schema_version) or schema_version.split(".", 1)[0] != "2":
        raise _error("root.schema_version", "must be a supported semver version with major version 2")
    generator_abi_version = raw.get("generator_abi_version")
    if generator_abi_version != GENERATOR_ABI_VERSION:
        raise _error(
            "root.generator_abi_version",
            f"must be {GENERATOR_ABI_VERSION}",
        )
    capabilities = raw.get("required_runtime_capabilities")
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) and item for item in capabilities
    ):
        raise _error("root.required_runtime_capabilities", "must be a list of strings")
    if len(capabilities) != len(set(capabilities)):
        raise _error("root.required_runtime_capabilities", "contains duplicates")
    raw_classes = raw.get("classes")
    if not isinstance(raw_classes, list) or not raw_classes:
        raise _error("root.classes", "must be a non-empty list")
    classes = tuple(_parse_class(item, f"root.classes[{index}]") for index, item in enumerate(raw_classes))
    required_capabilities = set(REQUIRED_RUNTIME_CAPABILITIES)
    if any(
        candidate.fields
        for cls in classes
        for candidate in (*cls.base_lineage, cls)
    ):
        required_capabilities.add(EXTERNAL_FIELD_STORAGE_CAPABILITY)
    missing = sorted(required_capabilities - set(capabilities))
    if missing:
        raise _error(
            "root.required_runtime_capabilities",
            "is missing required capabilities: " + ", ".join(missing),
        )
    class_ids = [cls.canonical_id for cls in classes]
    if len(class_ids) != len(set(class_ids)):
        raise _error("root.classes", "contains duplicate canonical class IDs")
    _validate_generated_names(classes)
    specializations: dict[tuple[str, str], str] = {}
    for cls in classes:
        if cls.specialization is None:
            continue
        key = (
            cls.symbol,
            json.dumps(_specialization_dict(cls.specialization), sort_keys=True),
        )
        existing = specializations.setdefault(key, cls.canonical_id)
        if existing != cls.canonical_id:
            raise _error(
                "root.classes",
                f"concrete specialization {cls.symbol} is assigned both {existing!r} and {cls.canonical_id!r}",
            )
    top_level = {cls.canonical_id: cls for cls in classes}
    for cls in classes:
        for index, ancestor in enumerate(cls.base_lineage):
            declared = top_level.get(ancestor.canonical_id)
            if declared is not None and replace(declared, base_lineage=()) != ancestor:
                raise _error(
                    f"root.classes[{cls.canonical_id}].base_lineage",
                    f"description for {ancestor.canonical_id!r} differs from its top-level target",
                )
            if declared is not None and declared.base_lineage and declared.base_lineage != cls.base_lineage[:index]:
                raise _error(f"root.classes[{cls.canonical_id}].base_lineage",
                             f"ancestry prefix for {ancestor.canonical_id!r} differs from its top-level target")
    manifest = Manifest(
        schema_uri,
        schema_version,
        generator_abi_version,
        tuple(capabilities),
        classes,
        provenance,
    )
    _manifest_lineage_contexts(manifest)
    if provenance is not None:
        validate_discovery_provenance(raw, source_path)
    return manifest


def projection_plan(target: ForeignClass) -> ProjectionPlan:
    """Resolve the minimal mirror/proxy portions for one declared target.

    ``base_lineage`` is deliberately retained as context instead of becoming a
    recursive generation list. This plan is the single place the generator uses
    to decide which language-boundary artifacts a target actually needs.
    """

    lineage = (*target.base_lineage, target)
    steps: list[ProjectionStep] = []
    for index, current in enumerate(lineage[:-1]):
        child = lineage[index + 1]
        if current.language == "sv" and child.language == "python":
            steps.append(
                ProjectionStep(
                    kind="sv_mirror",
                    source_class_id=current.canonical_id,
                    # The generated class keeps the foreign source's simple
                    # name.  Its generated package/module describes the
                    # boundary; ``Mirror`` is an implementation role, not a
                    # public type-name suffix.
                    generated_name=current.generated_name,
                    extends_class_id=current.canonical_id,
                )
            )
        elif current.language == "python" and child.language == "sv":
            # The proxy carries this Python class only because the following
            # SV class needs a real SV base portion for it.
            steps.append(
                ProjectionStep(
                    kind="sv_proxy",
                    source_class_id=current.canonical_id,
                    generated_name=current.generated_name,
                    extends_class_id=current.canonical_id,
                )
            )
    return ProjectionPlan(target.canonical_id, tuple(lineage), tuple(steps))


def projection_plans(manifest: Manifest) -> tuple[ProjectionPlan, ...]:
    """Return deterministic, target-only plans for the complete manifest."""

    return tuple(projection_plan(target) for target in manifest.classes)


def _manifest_lineage_contexts(manifest: Manifest) -> dict[str, tuple[ForeignClass, ...]]:
    declarations = {source.canonical_id: source for source in _all_manifest_classes(manifest)}
    contexts: dict[str, tuple[ForeignClass, ...]] = {}
    origins: dict[str, str] = {}
    for target in manifest.classes:
        lineage = (*target.base_lineage, target)
        for index, source in enumerate(lineage):
            # An omitted top-level lineage is unspecified context; ancestor
            # positions and explicit target lineages are complete graph evidence.
            if index == len(lineage) - 1 and not target.base_lineage:
                continue
            prefix = tuple(declarations[ancestor.canonical_id] for ancestor in lineage[:index])
            previous = contexts.setdefault(source.canonical_id, prefix)
            origin = origins.setdefault(source.canonical_id, target.canonical_id)
            if previous != prefix:
                previous_names = " -> ".join(ancestor.canonical_id for ancestor in previous) or "<root>"
                current_names = " -> ".join(ancestor.canonical_id for ancestor in prefix) or "<root>"
                raise SVXInheritanceError(
                    f"conflicting lineage ancestry for {source.canonical_id}: target {origin} "
                    f"has {previous_names}; target {target.canonical_id} has {current_names}"
                )
    return contexts


def _python_root_construction_plan(target: ForeignClass, *, manifest: Manifest | None = None) -> _PythonRootConstructionPlan:
    if manifest is not None:
        declarations = {source.canonical_id: source for source in _all_manifest_classes(manifest)}
        declared = declarations.get(target.canonical_id)
        if declared is None or declared != replace(target, base_lineage=()):
            raise SVXInheritanceError(f"construction source is missing or differs from manifest context: {target.canonical_id}")
        prefix = _manifest_lineage_contexts(manifest).get(target.canonical_id, target.base_lineage)
        target = replace(target, base_lineage=prefix)
    lineage = projection_plan(target).lineage
    if lineage[0].language != "python":
        raise SVXInheritanceError("Python-root construction plan requires a Python logical root")
    preceding_python = next((source for source in reversed(lineage[:-1]) if source.language == "python"), None)
    return _PythonRootConstructionPlan(lineage[0], tuple(lineage[:-1]),
                                       tuple(source for source in lineage[1:] if source.language == "python"),
                                       preceding_python)


def _sv_root_construction_plan(source: ForeignClass, *, manifest: Manifest) -> _SVRootConstructionPlan:
    declarations = {item.canonical_id: item for item in _all_manifest_classes(manifest)}
    if declarations.get(source.canonical_id) != replace(source, base_lineage=()):
        raise SVXInheritanceError(f"construction source differs from manifest context: {source.canonical_id}")
    ancestors = _manifest_lineage_contexts(manifest).get(source.canonical_id, source.base_lineage)
    lineage = (*ancestors, source)
    root = lineage[0]
    if root.language != "sv":
        raise SVXInheritanceError("SV-root construction requires an SV logical root")
    first_python = next((item for item in lineage if item.language == "python"), None)
    bridge_root = lineage[lineage.index(first_python) - 1] if first_python is not None else source
    if first_python is None:
        candidates = {}
        for plan in projection_plans(manifest):
            if plan.lineage[0].canonical_id == root.canonical_id:
                candidate = next((item for item in plan.lineage if item.language == "python"), None)
                if candidate is not None and plan.lineage[plan.lineage.index(candidate) - 1].canonical_id == bridge_root.canonical_id:
                    candidates[candidate.canonical_id] = candidate
        first_python = next(iter(candidates.values())) if len(candidates) == 1 else None
    python_sources = tuple(item for item in lineage if item.language == "python")
    return _SVRootConstructionPlan(root, bridge_root, tuple(ancestors), first_python, python_sources[1:],
                                  next((item for item in reversed(ancestors) if item.language == "python"), None))


def _sv_root_artifact_portions(manifest: Manifest) -> tuple[ForeignClass, ...]:
    declarations = {source.canonical_id: source for source in _all_manifest_classes(manifest)}
    selected = set()
    for plan in projection_plans(manifest):
        if plan.lineage[0].language != "sv" or not plan.steps:
            continue
        selected.update(step.source_class_id for step in plan.steps)
        target = plan.lineage[-1]
        if target.language == "sv" and target.constructor is not None:
            selected.add(target.canonical_id)
    return tuple(declarations[class_id] for class_id in sorted(selected))


def _require_executable_projection_plans(manifest: Manifest, *, separate_package_layout: bool = True) -> None:
    for plan in projection_plans(manifest):
        if plan.lineage[0].language == "python" and plan.steps:
            chain = " -> ".join(cls.canonical_id for cls in plan.lineage)
            raise SVXInheritanceError(
                f"Python-root alternating lineage is not implemented in public generation for target "
                f"{plan.target_class_id}: {chain}. Public root proxy "
                "construction/companion bridge integration for complete targets remains an implementation gap; "
                "internal staged-construction evidence is not a complete consumer workflow. "
                "an SV ancestor is not required by the inheritance design."
            )
    if separate_package_layout:
        _validate_separate_projection_package_layout(manifest)


def _validate_separate_projection_package_layout(manifest: Manifest) -> None:
    """Check declaration order, not the validity of the logical inheritance."""
    dependencies: dict[str, set[str]] = {}
    owners: dict[tuple[str, str], set[str]] = {}

    def depend(package: str, prerequisite: str, target_id: str) -> None:
        dependencies.setdefault(package, set()).add(prerequisite)
        dependencies.setdefault(prerequisite, set())
        owners.setdefault((package, prerequisite), set()).add(target_id)

    for plan in projection_plans(manifest):
        mirror = None
        for current, child in zip(plan.lineage, plan.lineage[1:]):
            if current.language == "sv" and child.language == "python":
                mirror = current
                depend(_projection_helper_package(current, "mirror"), current.symbol.split("::")[0], plan.target_class_id)
            elif current.language == "python" and child.language == "sv":
                proxy_package = _projection_helper_package(current, "proxy")
                if mirror is not None:
                    depend(proxy_package, _projection_helper_package(mirror, "mirror"), plan.target_class_id)
                depend(child.symbol.split("::")[0], proxy_package, plan.target_class_id)
            elif current.language == child.language == "sv":
                parent_package, child_package = current.symbol.split("::")[0], child.symbol.split("::")[0]
                if parent_package != child_package:
                    depend(child_package, parent_package, plan.target_class_id)

    visited = set()
    active = []

    def visit(package: str) -> None:
        if package in active:
            cycle = [*active[active.index(package):], package]
            targets = sorted({target for edge in zip(cycle, cycle[1:]) for target in owners[edge]})
            raise SVXInheritanceError(
                "SystemVerilog helper package layout requires a declaration cycle: "
                + " -> ".join(cycle) + "; targets: " + ", ".join(targets)
                + ". The logical lineage is valid, but separate-package source anchors cannot materialize it. "
                "Source-managed inline projection integration remains an implementation gap; "
                "this is not a requirement to split user classes into different packages or modules."
            )
        if package in visited:
            return
        active.append(package)
        for prerequisite in sorted(dependencies[package]):
            visit(prerequisite)
        active.pop()
        visited.add(package)

    for package in sorted(dependencies):
        visit(package)


def _projected_class_ids(manifest: Manifest) -> set[str]:
    """Classes represented by an explicit alternating-lineage helper path.

    A lineage owns its generated bridge classes.  This prevents a target-only
    projection from manufacturing a competing representation for one of its
    ancestors; for example, an SV base crossing to Python is represented by
    ``AMirror`` exactly once.
    """

    projected: set[str] = set()
    for plan in projection_plans(manifest):
        if plan.steps:
            projected.update(cls.canonical_id for cls in plan.lineage)
    return projected


def _all_manifest_classes(manifest: Manifest) -> tuple[ForeignClass, ...]:
    """Return one canonical declaration for every target or lineage member."""

    resolved: dict[str, ForeignClass] = {}
    origins: dict[str, str] = {}
    for target in manifest.classes:
        for cls in (*target.base_lineage, target):
            cls = replace(cls, base_lineage=())
            previous = resolved.setdefault(cls.canonical_id, cls)
            origin = origins.setdefault(cls.canonical_id, target.canonical_id)
            if previous != cls:
                differences = ", ".join(field.name for field in dataclass_fields(ForeignClass)
                                        if getattr(previous, field.name) != getattr(cls, field.name))
                raise SVXInheritanceError(
                    f"conflicting lineage declarations for {cls.canonical_id} between targets "
                    f"{origin} and {target.canonical_id}; differing declaration fields: {differences}"
                )
    return tuple(resolved[key] for key in sorted(resolved))


def migrate_manifest(data: Any) -> dict[str, Any]:
    """Upgrade the executable v1 type syntax to the declarative v2 schema."""

    migrated = json.loads(json.dumps(data))
    def migrate_class(cls: Any) -> None:
        if not isinstance(cls, dict):
            return
        constructor = cls.get("constructor")
        groups = [constructor.get("parameters", [])] if isinstance(constructor, dict) else []
        for method in cls.get("methods", []):
            if not isinstance(method, dict):
                continue
            groups.append(method.get("parameters", []))
            method["return_type"] = _migrate_type_binding(
                method.get("return_type"), "method.return_type"
            )
        for parameters in groups:
            if not isinstance(parameters, list):
                continue
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                parameter["type"] = _migrate_type_binding(
                    parameter.get("type"), "parameter.type"
                )
        for base in cls.get("base_lineage", []):
            migrate_class(base)

    for cls in migrated.get("classes", []):
        migrate_class(cls)
    migrated["schema_uri"] = SCHEMA_URI
    migrated["schema_version"] = SCHEMA_VERSION
    migrated["generator_abi_version"] = GENERATOR_ABI_VERSION
    migrated["required_runtime_capabilities"] = list(
        REQUIRED_RUNTIME_CAPABILITIES
    )
    parse_manifest(migrated)
    return migrated


def load_manifest(path: Path) -> Manifest:
    try:
        data = json.loads(path.read_text())
    except OSError as error:
        raise SVXInheritanceError(f"cannot read inheritance manifest {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SVXInheritanceError(f"invalid JSON inheritance manifest {path}: {error.msg}") from error
    return parse_manifest(data, source_path=path)


def _python_module_for(cls: ForeignClass) -> str:
    module = "svx_mirror." + ".".join(cls.symbol.split("::")[:-1])
    return module


def _sv_package_for(cls: ForeignClass) -> str:
    # Public SV projections intentionally use only the final Python module
    # component.  A collision is a manifest error rather than an opaque hash.
    return "svx_proxy_" + cls.symbol.split(".")[-2]


def _python_reverse_module_for(cls: ForeignClass) -> str:
    return "svx_py." + ".".join(cls.symbol.split(".")[:-1])


def _public_python_type_for(cls: ForeignClass) -> str | None:
    """Return the public generated Python type for an SV source class."""

    if cls.language != "sv":
        return None
    return f"{_python_module_for(cls)}.{cls.generated_name}"


def _public_sv_type_for(cls: ForeignClass) -> str | None:
    """Return the public generated SV type for a Python source class."""

    if cls.language != "python":
        return None
    return f"{_sv_package_for(cls)}::{cls.generated_name}"


def _python_adapter_type_for(cls: ForeignClass) -> str | None:
    """Return the generated Python runtime adapter for a Python source class."""

    if cls.language != "python":
        return None
    return f"{_python_reverse_module_for(cls)}.{cls.generated_name}"


def _validate_generated_names(classes: tuple[ForeignClass, ...]) -> None:
    seen: dict[tuple[str, str, str], ForeignClass] = {}
    for cls in classes:
        if cls.language == "sv":
            namespace = _python_module_for(cls)
            target = "Python"
        else:
            namespace = _sv_package_for(cls)
            target = "SystemVerilog"
        key = (target, namespace, cls.generated_name)
        previous = seen.get(key)
        if previous is not None:
            raise _error(
                "root.classes",
                f"generated {target} name {namespace}.{cls.generated_name} collides between "
                f"{previous.canonical_id!r} and {cls.canonical_id!r}",
            )
        seen[key] = cls


def _python_parameter_list(method: Method) -> str:
    return _python_request_parameter_list(method)


def _python_receiver(method: Method) -> str:
    return _sv_generated_names({p.name for p in method.parameters}, ("self",))["self"]


def _python_request_parameter_list(method: Method, *, include_self: bool = True) -> str:
    parameters = [parameter.name for parameter in method.parameters]
    if include_self:
        parameters.insert(0, _python_receiver(method))
    return ", ".join(parameters)


def _emit_python_bridge_method(method: Method, class_id: str | None = None, *, local_import: bool = False) -> list[str]:
    static = method.is_static and class_id is not None
    bridge = "invoke_sv_static" if static else "invoke_sv"
    occupied = {p.name for p in method.parameters}
    alias = _sv_generated_names(occupied, (bridge,))[bridge]
    receiver = _python_receiver(method)
    signature = (_python_static_request_parameter_list(method) if static
                 else _python_request_parameter_list(method))
    lines = [""]
    if static:
        lines.append("    @staticmethod")
    lines.append(f"    def {method.name}({signature}):")
    if local_import or alias != bridge:
        lines.append(f"        from svx.inheritance import {bridge} as {alias}")
    target = repr(class_id) if static else f"{receiver}._svx_remote_object_id"
    lines.append(f"        return {alias}({target}, {method.canonical_id!r}, {_request_values_repr(method)})")
    return lines


def _python_constructor_scope(parameters: tuple[Parameter, ...], *, mirror: bool = False):
    names = _sv_generated_names(
        {parameter.name for parameter in parameters},
        ("self", "_native", "encode_constructor", "bind_instance", "object_id", "SVMirror"),
    )
    imports = []
    for name, module in (("_native", "svx"), ("encode_constructor", "svx.inheritance"),
                         ("bind_instance", "svx.inheritance"), ("SVMirror", "svx.declarations")):
        if names[name] != name and (name != "SVMirror" or mirror):
            imports.append(f"        from {module} import {name} as {names[name]}")
    signature = ", ".join([names["self"], *(p.name for p in parameters)])
    return names, signature, imports


def _binding_repr(binding: TypeBinding) -> str:
    return repr(binding.runtime_spec())


def _type_specs(method: Method) -> str:
    return ", ".join(_binding_repr(parameter.type_binding) for parameter in method.parameters)


def _field_specs(parameters: tuple[Parameter, ...]) -> str:
    fields = ", ".join(
        repr((parameter.name, parameter.type_binding.runtime_spec()))
        for parameter in parameters
    )
    return f"({fields}{',' if len(parameters) == 1 else ''})"


def _constructor_registration(cls: ForeignClass, *, function_name: str = "register_constructor") -> str:
    assert cls.constructor is not None
    targets = tuple(p.handle.target_type_name for p in cls.constructor.parameters if p.handle is not None)
    extra = f", external_targets={targets!r}" if targets else ""
    return f"{function_name}({cls.canonical_id!r}, {_field_specs(cls.constructor.parameters)}{extra})"


def _return_slot_name(parameter_names: Iterable[str]) -> str:
    occupied = set(parameter_names)
    candidate = _RETURN_FIELD_NAME
    suffix = 0
    while candidate in occupied:
        suffix += 1
        candidate = f"{_RETURN_FIELD_NAME}_{suffix}"
    return candidate


def _method_return_slot(method: Method) -> str:
    return _return_slot_name(parameter.name for parameter in method.parameters)


def _response_field_specs(method: Method) -> str:
    fields = [
        (parameter.name, parameter.type_binding.runtime_spec())
        for parameter in _response_parameters(method)
    ]
    if method.return_type is not None:
        fields.append((_method_return_slot(method), method.return_type.runtime_spec()))
    content = ", ".join(repr(field) for field in fields)
    return f"({content}{',' if len(fields) == 1 else ''})"


def _contract_data(method: Method) -> dict[str, Any]:
    """Return the runtime contract with a stable, readable field order."""

    external_targets = tuple(
        handle.target_type_name
        for handle in (
            *(parameter.handle for parameter in method.parameters),
            method.return_handle,
        )
        if handle is not None
    )
    return {
        "timing": method.timing,
        "parameters": tuple(
            (parameter.name, parameter.direction, parameter.type_binding.runtime_spec())
            for parameter in method.parameters
        ),
        "request": tuple(
            (parameter.name, parameter.type_binding.runtime_spec())
            for parameter in _request_parameters(method)
        ),
        "response": tuple(
            (parameter.name, parameter.type_binding.runtime_spec())
            for parameter in _response_parameters(method)
        ) + (
            ((_method_return_slot(method), method.return_type.runtime_spec()),)
            if method.return_type is not None
            else ()
        ),
        "external_targets": external_targets,
    }


def _register_contract_lines(methods: tuple[Method, ...] | list[Method], *, function_name: str = "register_contract") -> list[str]:
    """Format generated call contracts for review without changing their data."""

    rendered = pformat(
        {method.canonical_id: _contract_data(method) for method in methods},
        width=100,
        sort_dicts=False,
    )
    return [
        "# --- SvTypes call contracts (private bridge metadata) ---",
        f"{function_name}(",
        *(f"    {line}" for line in rendered.splitlines()),
        ")",
    ]


def _generated_python_header(
    manifest: Manifest, *, role: str, targets: tuple[str, ...] = ()
) -> list[str]:
    """Return deterministic provenance comments for one generated module."""

    lines = [
        "# Generated by svx inheritance-gen. Do not edit.",
        f"# Manifest: {manifest.schema_uri} v{manifest.schema_version}; generator ABI {manifest.generator_abi_version}.",
        f"# Role: {role}.",
    ]
    if targets:
        lines.append("# Targets: " + ", ".join(targets) + ".")
    return [*lines, ""]


def _generated_python_init(manifest: Manifest, role: str) -> str:
    return "\n".join(_generated_python_header(manifest, role=role))


def _python_callback_portions(lineage: tuple[ForeignClass, ...]) -> dict[str, str]:
    portions = {}
    for index, source in enumerate(lineage):
        start = index if source.language == 'python' else next(
            (position for position in range(index + 1, len(lineage))
             if lineage[position].language == 'python'), None)
        if start is None:
            continue
        end = start
        while end + 1 < len(lineage) and lineage[end + 1].language == 'python':
            end += 1
        if source.language == 'python' and end + 1 == len(lineage):
            continue
        # A base gateway must stay in its Python segment, not redispatch through
        # a later SV boundary into the final Python override.
        portions[source.canonical_id] = lineage[end].canonical_id
    return portions


def _emit_python_root_companion(manifest: Manifest, source: ForeignClass, *,
                                ancestor_sources: tuple[ForeignClass, ...] = (),
                                reserved_names: frozenset[str] = frozenset(),
                                include_preamble: bool = True,
                                initialize_owner_before_source: bool = False) -> str:
    """Emit the internal root owner portion, not a public complete-target factory."""
    if source.language != "python":
        raise SVXInheritanceError("Python-root companion requires a Python source class")
    module, name = source.symbol.rsplit(".", 1)
    field_ids = {}
    occupied = set(reserved_names) | {name}
    foreign_name = f"_Foreign{name}"
    foreign = _sv_generated_names(occupied, (foreign_name,))[foreign_name]
    occupied.add(foreign)
    base_classes = {source.canonical_id: foreign}
    ancestor_imports = []
    for index, ancestor in enumerate(ancestor_sources):
        if ancestor.language == "python":
            ancestor_module, ancestor_name = ancestor.symbol.rsplit(".", 1)
            requested_alias = f"_AncestorSource{index}"
            alias = _sv_generated_names(occupied, (requested_alias,))[requested_alias]
            occupied.add(alias)
            ancestor_imports.append(f"from {ancestor_module} import {ancestor_name} as {alias}")
            base_classes[ancestor.canonical_id] = alias
    for portion in (*ancestor_sources, source):
        for field in portion.fields:
            if field.name in field_ids:
                raise SVXInheritanceError("ambiguous Python-root companion field projection")
            field_ids[field.name] = portion.canonical_id + "." + field.name
    aliases = _sv_generated_names(occupied, (
        "_PythonRootOwner", "register_contract", "register_constructor", "register_python_subclass", "_source_signature", "_SourceSvObject", "_register_python_static_methods"
    ))
    initializer_indent = "    " if initialize_owner_before_source else "        "
    initializer_lines = [initializer_indent + line for line in [
        "def __init__(self, *args, **kwargs):",
        "    from svx.declarations import _PythonRootOwner as _Owner",
        f"    from {module} import {name} as _Source",
        "    _Owner.__init__(self)",
        "    _Source.__init__(self, *args, **kwargs)",
    ]]
    lines = [
        *(_generated_python_header(manifest, role="internal Python-root owner companion", targets=(source.canonical_id,))
          if include_preamble else []),
        *(["from __future__ import annotations"] if include_preamble else []),
        f"from {module} import {name} as {foreign}",
        *ancestor_imports,
        f"from inspect import signature as {aliases['_source_signature']}",
        f"from svtypes import SvObject as {aliases['_SourceSvObject']}",
        f"from svx.declarations import _PythonRootOwner as {aliases['_PythonRootOwner']}",
        *(f"from svx.inheritance import {function} as {aliases[function]}"
          for function in ("register_contract", "register_constructor", "register_python_subclass", "_register_python_static_methods")),
        "",
        *_register_contract_lines(source.methods, function_name=aliases["register_contract"]),
        (_constructor_registration(source, function_name=aliases["register_constructor"])
         if source.constructor is not None else f"{aliases['register_constructor']}({source.canonical_id!r}, ())"),
        "",
        f"class {name}({foreign}, {aliases['_PythonRootOwner']}):",
        f"    \"\"\"Internal paired owner portion for {source.symbol}.\"\"\"",
        f"    __signature__ = {aliases['_source_signature']}({foreign})",
        f"    __svx_foreign_class_id__ = {source.canonical_id!r}",
        "    __svx_python_base_classes__ = {" + ", ".join(f"{class_id!r}: {alias}" for class_id, alias in base_classes.items()) + "}",
        f"    __svx_python_callback_portions__ = {_python_callback_portions((*ancestor_sources, source))!r}",
        f"    __svx_root_field_ids__ = {field_ids!r}",
        f"    __svx_constructor_python_portions__ = {tuple(portion.canonical_id for portion in (*ancestor_sources, source) if portion.language == 'python')[1:]!r}",
        "",
        *([] if initialize_owner_before_source else [f"    if not issubclass({foreign}, {aliases['_SourceSvObject']}):"]),
        *initializer_lines,
        "",
        f"{aliases['register_python_subclass']}({source.canonical_id!r}, {name})",
        f"{aliases['_register_python_static_methods']}({source.canonical_id!r}, {foreign}, {tuple(method.canonical_id for method in source.methods if method.is_static)!r})",
        "",
    ]
    return "\n".join(lines)


def _generated_sv_header(manifest: Manifest) -> list[str]:
    """Return deterministic provenance comments for generated SV source."""

    return [
        "// Generated by svx inheritance-gen. Do not edit.",
        f"// Manifest: {manifest.schema_uri} v{manifest.schema_version}; generator ABI {manifest.generator_abi_version}.",
        "// Layout: SvTypes records, typed external handles, public projections, then lineage helpers.",
    ]


def _emit_python_root_sv_view(manifest: Manifest, source: ForeignClass, root: ForeignClass,
                              *, root_module: str, base_source: ForeignClass | None = None,
                              ancestor_sources: tuple[ForeignClass, ...] = (),
                              python_portions: tuple[ForeignClass, ...] = (),
                              reserved_names: frozenset[str] = frozenset(),
                              include_preamble: bool = True,
                              lineage_sources: tuple[ForeignClass, ...] | None = None) -> str:
    """Emit an internal direct-root SV view; public full-target integration is separate."""
    if source.language != "sv" or root.language != "python" or source.constructor is None:
        raise SVXInheritanceError("Python-root SV view requires an SV constructor and a Python root")
    aliases = _sv_generated_names(set(reserved_names) | {source.name}, ("_RootCompanion", "_codec_from_spec", "register_contract",
                                               "register_constructor", "register_python_subclass", "_register_source_mirror_implementation", "_Signature", "_Parameter"))
    parameters = source.constructor.parameters
    scope = _sv_generated_names({parameter.name for parameter in parameters},
                                ("self", "_create_root_target", "_encode_constructor", "_validate_staged_base_constructor", "_suspend_natural_constructor"))
    owner, create, encode, validate, suspend = scope.values()
    signature = ", ".join((owner, *(parameter.name for parameter in parameters)))
    values = "{" + ", ".join(f"{parameter.name!r}: {parameter.name}" for parameter in parameters) + "}"
    fields = {}
    lineage = lineage_sources if lineage_sources is not None else (root, *ancestor_sources, source)
    inherited_sv_sources = _unbridged_sv_ancestors(tuple(lineage[:-1]))
    surface_methods = {}
    for portion in (*inherited_sv_sources, source):
        for method in portion.methods:
            surface_methods[method.name] = (portion, method)
    contracts = tuple(method for portion in (*inherited_sv_sources, source) for method in portion.methods)
    for portion in lineage:
        for field in portion.fields:
            if field.name in fields:
                raise SVXInheritanceError("ambiguous Python-root field projection in the SV view")
            fields[field.name] = portion.canonical_id + "." + field.name
    callback_portions = _python_callback_portions(tuple(lineage))
    parameter_type = aliases["_Parameter"]
    display_parameters = ", ".join(f"{parameter_type}({parameter.name!r}, {parameter_type}.POSITIONAL_OR_KEYWORD)"
                                   for parameter in parameters)
    lines = [
        *(_generated_python_header(manifest, role="internal Python-root SV view", targets=(source.canonical_id,))
          if include_preamble else []),
        *(["from __future__ import annotations"] if include_preamble else []),
        f"from {root_module} import {(base_source or root).name} as {aliases['_RootCompanion']}",
        f"from inspect import Signature as {aliases['_Signature']}, Parameter as {aliases['_Parameter']}",
        *(f"from svx.inheritance import {function} as {aliases[function]}"
          for function in ("_codec_from_spec", "register_contract", "register_constructor", "register_python_subclass")),
        f"from svx.declarations import _register_source_mirror_implementation as {aliases['_register_source_mirror_implementation']}",
        "",
        *_register_contract_lines(contracts, function_name=aliases["register_contract"]),
        _constructor_registration(source, function_name=aliases["register_constructor"]),
        "",
        f"class {source.name}({aliases['_RootCompanion']}):",
        f"    \"\"\"Internal paired Python view of {source.symbol}.\"\"\"",
        f"    __signature__ = {aliases['_Signature']}([{display_parameters}])",
        f"    __svx_foreign_class_id__ = {source.canonical_id!r}",
        f"    __svx_root_field_ids__ = {fields!r}",
        "    __svx_guard_descendant_initializers__ = True",
        f"    __svx_constructor_python_portions__ = {tuple(portion.canonical_id for portion in python_portions)!r}",
        f"    __svx_python_callback_portions__ = {callback_portions!r}",
        *(f"    {field.name} = {aliases['_codec_from_spec']}({field.type_binding.runtime_spec()!r})"
          for portion in (*inherited_sv_sources, source) for field in portion.fields),
        "",
        f"    def __init__({signature}):",
        f"        from svx.inheritance import _suspend_natural_constructor as {suspend}",
        f"        if {suspend}({owner}, {source.canonical_id!r}, {values}):",
        "            return",
        f"        if {owner}._svx_remote_object_id is not None:",
        f"            from svx.inheritance import _validate_staged_base_constructor as {validate}",
        f"            {validate}({owner}, {source.canonical_id!r}, {values})",
        "            return",
    ]
    lines.extend([
        f"        from svx.inheritance import _create_sv_with_python_root as {create}, encode_constructor as {encode}",
        f"        {create}({owner}, {root.canonical_id!r}, {source.canonical_id!r}, {encode}({source.canonical_id!r}, {values}){', python_portions=' + repr(tuple(portion.canonical_id for portion in python_portions)) if python_portions else ''})",
    ])
    for portion, method in surface_methods.values():
        lines.extend(_emit_python_bridge_method(method, portion.canonical_id, local_import=True))
    lines.extend(["", f"{aliases['register_python_subclass']}({source.canonical_id!r}, {source.name})"])
    lines.append(f"{aliases['_register_source_mirror_implementation']}({source.canonical_id!r}, {source.name})")
    return "\n".join([*lines, ""])


def _request_values_repr(method: Method) -> str:
    entries = ", ".join(
        f"{parameter.name!r}: {parameter.name}"
        for parameter in method.parameters
    )
    return "{" + entries + "}"


def _emit_planned_python_root_companion(manifest: Manifest, source: ForeignClass) -> str:
    plan = _python_root_construction_plan(source, manifest=manifest)
    return _emit_python_root_companion(manifest, source, ancestor_sources=plan.ancestors)


def _emit_planned_python_root_sv_view(manifest: Manifest, source: ForeignClass,
                                     *, companion_modules: dict[str, str]) -> str:
    plan = _python_root_construction_plan(source, manifest=manifest)
    base = plan.preceding_python
    if base is None or base.canonical_id not in companion_modules:
        raise SVXInheritanceError(f"missing generated Python companion module for {source.canonical_id}")
    return _emit_python_root_sv_view(manifest, source, plan.root,
                                    root_module=companion_modules[base.canonical_id], base_source=base,
                                    ancestor_sources=plan.ancestors[1:], python_portions=plan.python_portions)


def _emit_python_root_module(manifest: Manifest, sources: tuple[ForeignClass, ...], *,
                             companion_modules: dict[str, str], defer_classes: bool = False) -> str:
    """Assemble requested portions in one module without duplicating ancestors."""
    names = [source.name for source in sources]
    if len(names) != len(set(names)):
        raise SVXInheritanceError("Python-root module contains duplicate public class names")
    planned = [(source, _python_root_construction_plan(source, manifest=manifest)) for source in sources]
    planned.sort(key=lambda item: (len(item[1].ancestors), item[0].canonical_id))
    reserved = frozenset(names)
    lines = [*_generated_python_header(manifest, role="internal Python-root module",
                                       targets=tuple(source.canonical_id for source, _ in planned)),
             "from __future__ import annotations", ""]
    deferred = {}
    for source, plan in planned:
        if source.language == "python":
            text = _emit_python_root_companion(manifest, source, ancestor_sources=plan.ancestors,
                                               reserved_names=reserved, include_preamble=False)
        else:
            base = plan.preceding_python
            if base is None or base.canonical_id not in companion_modules:
                raise SVXInheritanceError(f"missing generated Python companion module for {source.canonical_id}")
            text = _emit_python_root_sv_view(manifest, source, plan.root,
                                             root_module=companion_modules[base.canonical_id], base_source=base,
                                             ancestor_sources=plan.ancestors[1:], python_portions=plan.python_portions,
                                             reserved_names=reserved, include_preamble=False)
        if defer_classes:
            loader = _sv_generated_names(set(reserved) | set(deferred.values()), ('_svx_define_' + source.name,))['_svx_define_' + source.name]
            deferred[source.name] = loader
            lines.extend(_emit_deferred_python_class(source, text, loader))
        else:
            lines.extend([text.rstrip(), ""])
    lines.extend(_emit_deferred_python_footer(deferred))
    return "\n".join(lines)


def _python_root_artifact_portions(manifest: Manifest) -> tuple[ForeignClass, ...]:
    declarations = {source.canonical_id: source for source in _all_manifest_classes(manifest)}
    selected = set()
    for plan in projection_plans(manifest):
        if plan.lineage[0].language != "python":
            continue
        selected.update(step.source_class_id for step in plan.steps)
        target = plan.lineage[-1]
        if target.language == "sv" and target.constructor is not None:
            selected.add(target.canonical_id)
        elif len(plan.lineage) == 1 and target.constructor is not None and target.constructor.initiator == "sv":
            selected.add(target.canonical_id)
    return tuple(declarations[class_id] for class_id in sorted(selected))


def _emit_python_root_artifacts(manifest: Manifest, *, source_managed_layout: bool = False) -> dict[PurePosixPath, str]:
    """Derive Python-root module locations from requested projection edges."""
    portions = _python_root_artifact_portions(manifest)
    companion_modules = {source.canonical_id: _python_reverse_module_for(source)
                         for source in portions if source.language == "python"}
    grouped: dict[str, list[ForeignClass]] = {}
    for source in portions:
        module = companion_modules[source.canonical_id] if source.language == "python" else _python_module_for(source)
        grouped.setdefault(module, []).append(source)
    emitted = {}
    for module, sources in sorted(grouped.items()):
        parts = module.split(".")
        for depth in range(1, len(parts)):
            path = PurePosixPath(*parts[:depth], "__init__.py")
            emitted.setdefault(path, _generated_python_init(manifest, "Python-root generated package"))
        path = PurePosixPath(*parts).with_suffix(".py")
        emitted[path] = _emit_python_root_module(manifest, tuple(sources), companion_modules=companion_modules,
                                                defer_classes=source_managed_layout)
    emitted.update(_emit_python_vif_views(manifest))
    return emitted


def _introduced_python_virtuals(source: ForeignClass, ancestors: tuple[ForeignClass, ...]) -> tuple[Method, ...]:
    """Reuse ancestor callback bridges; a proxy adds only new virtual slots."""
    inherited = {method.name for ancestor in ancestors for method in ancestor.methods if method.virtual}
    return tuple(method for method in source.methods if method.virtual and method.name not in inherited)


def _effective_virtual_methods(source: ForeignClass, ancestors: tuple[ForeignClass, ...]) -> tuple[Method, ...]:
    """An inherited virtual slot remains virtual without a repeated declaration."""
    slots: dict[str, Method] = {}
    for portion in (*ancestors, source):
        for method in portion.methods:
            if not method.is_static and (method.virtual or method.name in slots):
                slots[method.name] = method if method.virtual else replace(method, virtual=True)
    return tuple(slots.values())


def _unbridged_sv_ancestors(ancestors: tuple[ForeignClass, ...]) -> tuple[ForeignClass, ...]:
    """Ordinary SV portions since the preceding Python proxy share this helper."""
    sources = []
    for ancestor in reversed(ancestors):
        if ancestor.language != 'sv':
            break
        sources.append(ancestor)
    return tuple(reversed(sources))


def _emit_planned_python_root_sv_projection(manifest: Manifest, source: ForeignClass,
                                           *, generated_name: str, base_type: str | None) -> list[str]:
    plan = _python_root_construction_plan(source, manifest=manifest)
    if source.canonical_id == plan.root.canonical_id:
        return _emit_sv_projection_class(generated_name, base_type, source, base_methods=(),
                                         dispatch_virtuals=source.methods, is_root_python_proxy=True,
                                         transparent_construction=True)
    callbacks = any(step.kind == "sv_mirror" and step.source_class_id == source.canonical_id
                    for target_plan in projection_plans(manifest) for step in target_plan.steps)
    dispatch_virtuals = ((_effective_virtual_methods(source, plan.ancestors) if callbacks else ())
                         if source.language == "sv" else _introduced_python_virtuals(source, plan.ancestors))
    return _emit_sv_projection_class(generated_name, base_type, source,
                                     base_methods=source.methods if source.language == "sv" else (),
                                     dispatch_virtuals=dispatch_virtuals,
                                     delegate_unmatched_to_super=True, reuse_base_object_id=True,
                                     super_accepts_object_id=True, staged_python_root=plan.root,
                                     constructor_python_portions=plan.python_portions,
                                     early_receiver_binding=True,
                                     natural_constructor_base=(next(item for item in reversed(plan.ancestors) if item.language == 'sv')
                                                               if source.language == 'python' else None),
                                     callback_boundary=source.canonical_id if source.language == 'sv' and callbacks else None,
                                     transparent_construction=source.language == 'sv',
                                     inherited_sv_sources=_unbridged_sv_ancestors(plan.ancestors) if source.language == 'sv' else ())


def _emit_python_root_sv_packages(manifest: Manifest, *, has_call_records: bool,
                                  has_external_handles: bool = False) -> dict[str, str]:
    """Materialize requested root portions in the normal public namespaces.

    Package blocks remain separate so source-anchor integration can place each
    before or after the actual user class. This does not open the public CLI
    gate until complete source layout and target construction are qualified.
    """
    return _emit_staged_sv_packages(manifest, _python_root_artifact_portions(manifest),
                                   _python_root_construction_plan, _emit_planned_python_root_sv_projection,
                                   has_call_records=has_call_records, has_external_handles=has_external_handles)


def _emit_staged_sv_packages(
    manifest: Manifest, portions: tuple[ForeignClass, ...],
    construction_plan: Callable[..., _PythonRootConstructionPlan | _SVRootConstructionPlan],
    projection_emitter: Callable[..., list[str]], *, has_call_records: bool,
    has_external_handles: bool,
) -> dict[str, str]:
    """Share normal package/factory layout without conflating constructor roots."""
    _validate_separate_projection_package_layout(manifest)
    grouped: dict[str, list[ForeignClass]] = {}
    for source in portions:
        kind = 'mirror' if source.language == 'sv' else 'proxy'
        grouped.setdefault(_projection_helper_package(source, kind), []).append(source)
    packages = {}
    registered_static_sources: set[str] = set()
    for package, sources in sorted(grouped.items()):
        guard = re.sub(r'[^A-Za-z0-9_]', '_', package.upper()) + '__SV'
        lines = [*_generated_sv_header(manifest), f'`ifndef {guard}', f'`define {guard}',
                 f'package {package};', '  import svx_pkg::*;', '  import svtypes_pkg::*;',
                 *_sv_value_package_imports(sources),
                 *(['  import svx_call_records_pkg::*;'] if has_call_records else []),
                 *(['  import svx_external_handles_pkg::*;'] if has_external_handles else [])]
        generated_names = {source.generated_name for source in sources}
        generated_names.update(source.generated_name + '_factory' for source in sources if source.language == 'sv')
        for source in sorted(sources, key=lambda item: item.canonical_id):
            plan = construction_plan(source, manifest=manifest)
            if source.canonical_id == plan.root.canonical_id and source.language == 'python':
                base_type = None
            elif source.language == 'sv':
                base_type = _sv_class_reference(source)
            else:
                ancestor = next(item for item in reversed(plan.ancestors) if item.language == 'sv')
                base_type = _projection_helper_package(ancestor, 'mirror') + '::' + ancestor.generated_name
            lines.extend(projection_emitter(
                manifest, source, generated_name=source.generated_name, base_type=base_type))
            if source.language == 'sv':
                if any(item.generated_name == source.generated_name + '_factory' for item in sources):
                    raise SVXInheritanceError(f'generated factory name collision in {package}: {source.generated_name}_factory')
                lines.extend(_emit_sv_projection_factory(source, source.generated_name, announce_receiver=True))
                for owner in (*_unbridged_sv_ancestors(plan.ancestors), source):
                    if owner.canonical_id in registered_static_sources or not any(method.is_static for method in owner.methods):
                        continue
                    names = _sv_generated_names(generated_names, (
                        owner.generated_name + '_static_gateway',
                        owner.generated_name + '_static_dispatch',
                        owner.generated_name + '_static_dispatcher',
                    ))
                    generated_names.update(names.values())
                    lines.extend(_emit_sv_static_gateway(
                        owner, gateway_name=names[owner.generated_name + '_static_gateway'],
                        dispatcher_name=names[owner.generated_name + '_static_dispatch'],
                        instance_name=names[owner.generated_name + '_static_dispatcher']))
                    registered_static_sources.add(owner.canonical_id)
        lines.extend([f'endpackage : {package}', f'`endif // {guard}', ''])
        packages[package] = '\n'.join(lines)
    return packages


def _emit_planned_sv_root_sv_projection(manifest: Manifest, source: ForeignClass, *,
                                        generated_name: str, base_type: str) -> list[str]:
    plan = _sv_root_construction_plan(source, manifest=manifest)
    if source.canonical_id == plan.bridge_root.canonical_id:
        return _emit_sv_projection_class(generated_name, base_type, source, base_methods=source.methods,
                                        dispatch_virtuals=_effective_virtual_methods(source, plan.ancestors), is_root_sv_mirror=True,
                                        staged_sv_root=plan.first_python, transparent_construction=True,
                                        dynamic_sv_root=True,
                                        inherited_sv_sources=_unbridged_sv_ancestors(plan.ancestors))
    if plan.first_python is None:
        raise SVXInheritanceError('staged non-root portion needs target-specific first-Python selection')
    callbacks = any(step.kind == 'sv_mirror' and step.source_class_id == source.canonical_id
                    for target in projection_plans(manifest) for step in target.steps)
    virtuals = ((_effective_virtual_methods(source, plan.ancestors) if callbacks else ())
                if source.language == 'sv' else _introduced_python_virtuals(source, plan.ancestors))
    return _emit_sv_projection_class(
        generated_name, base_type, source, base_methods=source.methods if source.language == 'sv' else (),
        dispatch_virtuals=virtuals, reuse_base_object_id=True, super_accepts_object_id=True,
        delegate_unmatched_to_super=True,
        staged_python_root=plan.first_python,
        constructor_python_portions=plan.python_portions,
        transparent_construction=source.language == 'sv',
        early_receiver_binding=True,
        natural_constructor_base=(next(item for item in reversed(plan.ancestors) if item.language == 'sv')
                                  if source.language == 'python' else None),
        callback_boundary=source.canonical_id if source.language == 'sv' and callbacks else None,
        inherited_sv_sources=_unbridged_sv_ancestors(plan.ancestors) if source.language == 'sv' else ())


def _emit_sv_root_sv_packages(manifest: Manifest, *, has_call_records: bool,
                              has_external_handles: bool = False) -> dict[str, str]:
    return _emit_staged_sv_packages(manifest, _sv_root_artifact_portions(manifest),
                                   _sv_root_construction_plan, _emit_planned_sv_root_sv_projection,
                                   has_call_records=has_call_records, has_external_handles=has_external_handles)


def _emit_deferred_python_class(source: ForeignClass, text: str, loader: str) -> list[str]:
    declaration_lines = text.rstrip().splitlines()
    class_index = next(index for index, line in enumerate(declaration_lines)
                       if line.startswith(f'class {source.name}('))
    # A source import can reenter after its earlier class is already available.
    declaration_lines[class_index:class_index] = [
        f'if {source.name!r} in globals():', f'    return globals()[{source.name!r}]',
    ]
    return [f'def {loader}():',
            f'    if {source.name!r} in globals(): return globals()[{source.name!r}]',
            *('    ' + line if line else '' for line in declaration_lines),
            f'    {source.name}.__qualname__ = {source.name!r}',
            f'    globals()[{source.name!r}] = {source.name}', f'    return {source.name}', '']


def _emit_deferred_python_footer(deferred: dict[str, str]) -> list[str]:
    if not deferred:
        return []
    lines = ['def __getattr__(name):']
    for name, loader in deferred.items():
        lines.extend([f'    if name == {name!r}:', f'        return {loader}()'])
    lines.extend(['    raise AttributeError(name)', '', 'def _svx_finalize_generated_types():'])
    for name in deferred:
        lines.append(f'    if {name!r} not in globals(): __getattr__({name!r})')
    return [*lines, '']


def _emit_source_python_artifacts(manifest: Manifest) -> dict[PurePosixPath, str]:
    """Assemble both logical root families in shared source-managed modules."""
    emitted = _emit_sv_root_artifacts(manifest, source_managed_layout=True,
                                      include_python_roots=True)
    emitted.update(_emit_python_vif_views(manifest))
    return emitted


def _emit_sv_root_artifacts(manifest: Manifest, *, source_managed_layout: bool = False,
                            include_python_roots: bool = False) -> dict[PurePosixPath, str]:
    """Materialize staged SV-root portions; public emitter integration is separate."""
    base_manifest = manifest
    if include_python_roots:
        if not source_managed_layout:
            raise SVXInheritanceError('mixed root artifacts require source-managed layout')
        sv_targets = {plan.target_class_id for plan in projection_plans(manifest)
                      if plan.lineage[0].language == 'sv' or not plan.steps}
        base_manifest = replace(manifest, classes=tuple(source for source in manifest.classes
                                                        if source.canonical_id in sv_targets))
    emitted = emit_python_mirrors(base_manifest, register_sv_subclasses=False, include_sv_ancestor_members=True,
                                 separate_package_layout=not source_managed_layout,
                                 reserve_direct_receiver=frozenset(
                                     _sv_root_construction_plan(source, manifest=manifest).bridge_root.canonical_id
                                     for source in _sv_root_artifact_portions(manifest)))
    grouped: dict[str, list[tuple[ForeignClass, _SVRootConstructionPlan | _PythonRootConstructionPlan]]] = {}
    modules: dict[str, str] = {}
    for source in _sv_root_artifact_portions(manifest):
        plan = _sv_root_construction_plan(source, manifest=manifest)
        if source.canonical_id == plan.bridge_root.canonical_id:
            continue
        if plan.first_python is None:
            raise SVXInheritanceError('staged artifact portion needs target-specific first-Python selection')
        module = _python_reverse_module_for(source) if source.language == 'python' else _python_module_for(source)
        modules[source.canonical_id] = module
        grouped.setdefault(module, []).append((source, plan))
    python_ids = set()
    if include_python_roots:
        for source in _python_root_artifact_portions(manifest):
            plan = _python_root_construction_plan(source, manifest=manifest)
            module = _python_reverse_module_for(source) if source.language == 'python' else _python_module_for(source)
            modules[source.canonical_id] = module
            python_ids.add(source.canonical_id)
            grouped.setdefault(module, []).append((source, plan))
    for module, sources in sorted(grouped.items()):
        names = frozenset(source.name for source, _plan in sources)
        if len(names) != len(sources):
            raise SVXInheritanceError('SV-root module contains duplicate public class names')
        path = PurePosixPath(*module.split('.')).with_suffix('.py')
        existing = emitted.get(path) if source_managed_layout else None
        independent_loaders = {}
        if existing:
            # Keep bridge roots and independent targets; replace only boundary
            # views owned by the staged receiver plan.
            retained = existing.splitlines()
            independent = [target for target in base_manifest.classes
                           if target.language == 'python' and not projection_plan(target).steps
                           and _python_reverse_module_for(target) == module and target.name not in names]
            existing_tree = ast.parse(existing)
            deferred_nodes = set()
            for target in independent:
                selected = [node for node in existing_tree.body
                            if (isinstance(node, ast.ClassDef) and node.name == target.name)
                            or (isinstance(node, ast.ImportFrom)
                                and node.module == target.symbol.rsplit('.', 1)[0]
                                and any(alias.name == target.name for alias in node.names))]
                text = '\n'.join('\n'.join(retained[node.lineno - 1:node.end_lineno]) for node in selected)
                loader = _sv_generated_names(set(names) | set(independent_loaders),
                                            ('_svx_define_' + target.name,))['_svx_define_' + target.name]
                independent_loaders[loader] = (target, text)
                deferred_nodes.update(node.lineno for node in selected)
            for node in reversed(existing_tree.body):
                obsolete = node.lineno in deferred_nodes or (isinstance(node, ast.ClassDef) and node.name in names)
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    call = node.value
                    obsolete |= (isinstance(call.func, ast.Name) and call.func.id in {
                                     'register_python_subclass', '_register_source_mirror_implementation'}
                                 and len(call.args) == 2 and isinstance(call.args[1], ast.Name)
                                 and call.args[1].id in names)
                if obsolete:
                    del retained[node.lineno - 1:node.end_lineno]
            existing = '\n'.join(retained)
        lines = ([existing.rstrip(), ''] if existing else
                 [*_generated_python_header(manifest, role='internal staged SV-root module'),
                  'from __future__ import annotations', ''])
        deferred = {}
        for loader, (target, text) in independent_loaders.items():
            deferred[target.name] = loader
            lines.extend(_emit_deferred_python_class(target, text, loader))
        for source, plan in sorted(sources, key=lambda item: (len(item[1].ancestors), item[0].canonical_id)):
            python_root = source.canonical_id in python_ids
            if source.language == 'python':
                text = _emit_python_root_companion(
                    manifest, source, ancestor_sources=plan.ancestors, reserved_names=names,
                    include_preamble=False, initialize_owner_before_source=(
                        not python_root and source.canonical_id == plan.first_python.canonical_id))
            else:
                base = plan.preceding_python
                if base is None or base.canonical_id not in modules:
                    raise SVXInheritanceError(f'missing staged SV-root companion for {source.canonical_id}')
                if python_root:
                    text = _emit_python_root_sv_view(
                        manifest, source, plan.root, root_module=modules[base.canonical_id],
                        base_source=base, ancestor_sources=plan.ancestors[1:],
                        python_portions=plan.python_portions, reserved_names=names, include_preamble=False)
                else:
                    text = _emit_python_root_sv_view(
                        manifest, source, plan.first_python, root_module=modules[base.canonical_id],
                        base_source=base, lineage_sources=(*plan.ancestors, source),
                        python_portions=plan.python_portions, reserved_names=names, include_preamble=False)
            if source_managed_layout:
                loader = _sv_generated_names(set(names) | set(deferred.values()), ('_svx_define_' + source.name,))['_svx_define_' + source.name]
                deferred[source.name] = loader
                lines.extend(_emit_deferred_python_class(source, text, loader))
            else:
                lines.extend([text.rstrip(), ''])
        lines.extend(_emit_deferred_python_footer(deferred))
        parts = module.split('.')
        for depth in range(1, len(parts)):
            emitted.setdefault(PurePosixPath(*parts[:depth], '__init__.py'), _generated_python_init(manifest, 'staged SV-root package'))
        emitted[PurePosixPath(*parts).with_suffix('.py')] = '\n'.join(lines)
    return emitted


def _python_static_request_parameter_list(method: Method) -> str:
    return ", ".join(parameter.name for parameter in method.parameters)


def _request_parameters(method: Method) -> tuple[Parameter, ...]:
    return tuple(
        parameter
        for parameter in method.parameters
        if parameter.direction in {"input", "inout"}
    )


def _response_parameters(method: Method) -> tuple[Parameter, ...]:
    return tuple(
        parameter
        for parameter in method.parameters
        if parameter.direction in {"output", "inout"}
    )


def _vif_module_parts(binding: HandleBinding) -> tuple[str, ...]:
    assert binding.kind == "virtual_interface"
    stem = binding.target_type_name.removeprefix("sv-vif://")
    interface, separator, modport = stem.partition("/")
    if not separator or not interface or not modport:
        raise SVXInheritanceError(
            f"invalid virtual-interface target {binding.target_type_name!r}"
        )
    return ("svx_vif", interface, modport)


def _vif_view_class_name(binding: HandleBinding) -> str:
    return _vif_module_parts(binding)[-1][:1].upper() + _vif_module_parts(binding)[-1][1:]


def emit_python_mirrors(manifest: Manifest, *, register_sv_subclasses: bool = True,
                        include_sv_ancestor_members: bool = True,
                        separate_package_layout: bool = True,
                        reserve_direct_receiver: bool | frozenset[str] = False) -> dict[PurePosixPath, str]:
    """Return relative output paths and declaration-only Python mirror source."""

    _require_executable_projection_plans(manifest, separate_package_layout=separate_package_layout)
    projected = _projected_class_ids(manifest)
    modules: dict[str, list[ForeignClass]] = {}
    field_mirrors = {
        cls.canonical_id for cls in manifest.classes
        if cls.language == "sv" and (cls.fields or cls.constructor is not None)
        and cls.canonical_id not in projected
    }
    for cls in manifest.classes:
        if cls.language == "sv" and cls.canonical_id not in projected | field_mirrors:
            modules.setdefault(_python_module_for(cls), []).append(cls)

    emitted: dict[PurePosixPath, str] = {}
    if modules:
        emitted[PurePosixPath("svx_mirror/__init__.py")] = _generated_python_init(
            manifest, "generated SystemVerilog mirror package"
        )
    for module_name, classes in sorted(modules.items()):
        module_parts = module_name.split(".")
        path = PurePosixPath(*module_parts).with_suffix(".py")
        lines = [
            *_generated_python_header(
                manifest,
                role="Python mirrors for SystemVerilog-owned classes",
                targets=tuple(cls.canonical_id for cls in sorted(classes, key=lambda item: item.name)),
            ),
            "from __future__ import annotations",
            "from svx import _native",
            "from svx.inheritance import bind_instance, encode_constructor, invoke_sv, invoke_sv_static, register_constructor, register_contract, register_python_subclass, unbind_instance",
            "",
        ]
        for cls in sorted(classes, key=lambda item: item.name):
            lines.extend(_register_contract_lines(cls.methods))
            if cls.constructor is not None:
                lines.append("# --- Construction contract ---")
                lines.append(
                    _constructor_registration(cls)
                )
            if cls.constructor is not None and cls.constructor.initiator == "sv":
                lines.append("")
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init_subclass__(cls, **kwargs):", "        super().__init_subclass__(**kwargs)", f"        register_python_subclass({cls.canonical_id!r}, cls)", "", "    @classmethod", "    def __svx_create_from_sv__(cls, remote_object_id: int, *args):", "        instance = cls.__new__(cls)", "        instance._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, instance)", "        try:", "            cls.__init__(instance, *args)", "        except BaseException:", "            unbind_instance(remote_object_id)", "            raise", "        return instance", "", "    def __init__(self, *args):", "        if not hasattr(self, '_svx_remote_object_id'):", "            raise TypeError('SV-initiated inheritance instances must be created by SV')"])
            elif cls.constructor is not None and cls.constructor.initiator == "python":
                scope, signature, imports = _python_constructor_scope(cls.constructor.parameters)
                owner, native, encode, bind = (scope[name] for name in ("self", "_native", "encode_constructor", "bind_instance"))
                constructor_values = "{" + ", ".join(
                    f"{parameter.name!r}: {parameter.name}"
                    for parameter in cls.constructor.parameters
                ) + "}"
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init_subclass__(cls, **kwargs):", "        super().__init_subclass__(**kwargs)", f"        register_python_subclass({cls.canonical_id!r}, cls)", "", f"    def __init__({signature}):", *imports, f"        {owner}._svx_remote_object_id = {native}.inheritance_create_sv({cls.canonical_id!r}, {encode}({cls.canonical_id!r}, {constructor_values}))", "        try:", f"            {bind}({owner}._svx_remote_object_id, {owner})", "        except BaseException:", f"            {native}.inheritance_close({owner}._svx_remote_object_id)", "            raise"])
            else:
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init__(self, remote_object_id: int):", "        self._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, self)"])
            if not cls.methods:
                lines.append("    pass")
            for method in cls.methods:
                lines.extend(_emit_python_bridge_method(method, cls.canonical_id))
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"

    # Python counterparts of SV AMirror portions.  They are emitted only for
    # actual SV->Python boundaries and become the natural Python base imported
    # by user classes; no legacy foreign-name proxy is involved.
    projection_modules: dict[str, list[ForeignClass]] = {}
    # A directly requested SV class uses the same construction and field
    # endpoints as a boundary mirror, even without fields or a child target.
    # Reuse the common owner/binding lifecycle, without adding
    # a synthetic Python class to the manifest or changing SV generation scope.
    for cls in manifest.classes:
        if cls.canonical_id in field_mirrors:
            projection_modules.setdefault(_python_module_for(cls), []).append(cls)
    projected_python_contracts: dict[str, dict[str, Method]] = {}
    # ``SVXFieldStorage`` is bound by the generated mirror which constructs
    # the final Python portion.  That is not always the first mirror in an
    # alternating chain: for A(SV) -> B(Python) -> C(SV) -> D(Python), D is
    # constructed through CMirror, while B's fields physically live in the
    # inherited BProxy portion of the same C/D SV object.  Keep the map on the
    # mirror that owns the Python construction path, keyed by the concrete
    # Python target class ID.
    projected_python_fields: dict[str, dict[str, dict[str, str]]] = {}
    for plan in projection_plans(manifest):
        active_mirror: ForeignClass | None = None
        proxy_sources: list[ForeignClass] = []
        for step in plan.steps:
            source = next(
                cls for cls in plan.lineage if cls.canonical_id == step.source_class_id
            )
            if step.kind == "sv_mirror":
                active_mirror = source
                module = "svx_mirror." + "_".join(source.symbol.split("::")[:-1])
                projection_modules.setdefault(module, []).append(source)
            elif step.kind == "sv_proxy":
                proxy_sources.append(source)
                if active_mirror is not None:
                    contracts = projected_python_contracts.setdefault(active_mirror.canonical_id, {})
                    contracts.update((method.canonical_id, method) for method in source.methods)

        selected_fields = {
            field.name: f"{source.canonical_id}.{field.name}"
            for source in proxy_sources
            for field in source.fields
        }
        sv_fields = {
            field.name: f"{source.canonical_id}.{field.name}"
            for source in plan.lineage if source.language == "sv"
            for field in source.fields
        }
        selected_fields = {**sv_fields, **selected_fields}
        if not selected_fields:
            continue
        target = plan.lineage[-1]
        if target.language == "python":
            # The last SV mirror is the entry point for the final Python
            # target. It must bind every earlier Python portion projected into
            # the final SV object, not merely fields belonging to its direct
            # Python predecessor.
            if active_mirror is None:
                raise SVXInheritanceError(
                    f"cannot bind projected fields for {target.canonical_id} without an SV mirror"
                )
            projected_python_fields.setdefault(active_mirror.canonical_id, {})[
                target.canonical_id
            ] = selected_fields
        else:
            # An SV target is constructed through the mirror immediately
            # preceding each Python-to-SV edge. That mirror constructs the
            # corresponding Python class during the inherited SV constructor.
            active_mirror = None
            resident_sv_fields: dict[str, str] = {}
            for step in plan.steps:
                source = next(
                    cls for cls in plan.lineage if cls.canonical_id == step.source_class_id
                )
                if step.kind == "sv_mirror":
                    active_mirror = source
                    resident_sv_fields.update({
                        field.name: f"{source.canonical_id}.{field.name}"
                        for field in source.fields
                    })
                elif step.kind == "sv_proxy" and active_mirror is not None:
                    projected_python_fields.setdefault(active_mirror.canonical_id, {})[
                        source.canonical_id
                    ] = {
                        **resident_sv_fields,
                        **{field.name: f"{source.canonical_id}.{field.name}"
                           for field in source.fields},
                    }
    if projection_modules:
        emitted[PurePosixPath("svx_mirror/__init__.py")] = _generated_python_init(
            manifest, "generated SystemVerilog mirror package"
        )
    lineage_contexts = _manifest_lineage_contexts(manifest)
    for module, sources in sorted(projection_modules.items()):
        python_static_sources = tuple(
            source for source in _all_manifest_classes(manifest)
            if source.language == 'python' and any(method.is_static for method in source.methods)
        )
        member_sources = {
            source.canonical_id: (*_unbridged_sv_ancestors(lineage_contexts.get(source.canonical_id, source.base_lineage)), source)
            if include_sv_ancestor_members else (source,)
            for source in sources
        }
        path = PurePosixPath(*module.split(".")).with_suffix(".py")
        lines = [
            *_generated_python_header(
                manifest,
                role="executable Python AMirror bases for SystemVerilog-owned classes",
                targets=tuple(source.canonical_id for source in sorted(sources, key=lambda item: item.canonical_id)),
            ),
            "from __future__ import annotations",
            "from svx import _native",
            "from svx.declarations import SVMirror, _register_source_mirror_implementation",
            "from svx.inheritance import bind_instance, encode_constructor, invoke_sv, invoke_sv_static, register_constructor, register_contract, register_python_subclass",
            *(["from svx.inheritance import _register_python_static_source"] if python_static_sources else []),
            *(["from svx.inheritance import _codec_from_spec"]
              if any(portion.fields for source in sources
                     for portion in (*lineage_contexts.get(source.canonical_id, source.base_lineage), source)) else []),
            "",
        ]
        for source in python_static_sources:
            methods = tuple(method.canonical_id for method in source.methods if method.is_static)
            lines.append(f"_register_python_static_source({source.canonical_id!r}, {source.symbol!r}, {methods!r})")
        seen: set[str] = set()
        for source in sorted(sources, key=lambda item: item.canonical_id):
            if source.canonical_id in seen:
                continue
            seen.add(source.canonical_id)
            portions = member_sources[source.canonical_id]
            surface_methods = {method.name: (portion, method) for portion in portions for method in portion.methods}
            field_portions = (*lineage_contexts.get(source.canonical_id, source.base_lineage), source)
            source_fields = {field.name: (portion, field) for portion in portions for field in portion.fields}
            physical_field_ids = {field.name: f'{portion.canonical_id}.{field.name}'
                                  for portion in field_portions for field in portion.fields}
            lines.extend(_register_contract_lines(tuple(method for portion in portions for method in portion.methods)))
            contracts = projected_python_contracts.get(source.canonical_id, {})
            lines.extend(_register_contract_lines([contracts[key] for key in sorted(contracts)]))
            parameters = source.constructor.parameters if source.constructor else ()
            if source.constructor is not None:
                lines.append("# --- Construction contract ---")
                lines.append(_constructor_registration(source))
            scope, signature, imports = _python_constructor_scope(parameters, mirror=True)
            owner, native, encode, bind, object_id, base = (scope[name] for name in
                ("self", "_native", "encode_constructor", "bind_instance", "object_id", "SVMirror"))
            values = "{" + ", ".join(f"{p.name!r}: {p.name}" for p in parameters) + "}"
            mirror_name = source.generated_name
            direct_receiver = (reserve_direct_receiver is True
                               or isinstance(reserve_direct_receiver, frozenset)
                               and source.canonical_id in reserve_direct_receiver)
            field_maps = projected_python_fields.get(source.canonical_id, {})
            # A constructorless standalone view wraps an existing endpoint;
            # its subclasses must not alter the SV construction selector.
            # Alternating mirrors register only direct Python extensions.
            subclass_registration = [] if (
                not register_sv_subclasses or source.canonical_id in field_mirrors and source.constructor is None
            ) else [
                "    def __init_subclass__(cls, **kwargs):",
                "        super().__init_subclass__(**kwargs)",
                f"        if any(base is {mirror_name} or base.__dict__.get('__svx_sv_mirror__', {{}}).get('canonical_id') == {source.canonical_id!r} for base in cls.__bases__):",
                f"            register_python_subclass({source.canonical_id!r}, cls)",
                "",
            ]
            lines.extend(
                [
                    "",
                    f"class {mirror_name}(SVMirror):",
                    f"    \"\"\"Executable Python base view of {source.symbol}.\"\"\"",
                    *(f"    {field.name} = _codec_from_spec({field.type_binding.runtime_spec()!r})"
                      for _portion, field in source_fields.values()),
                    f"    __svx_foreign_class_id__ = {source.canonical_id!r}",
                    *(["    __svx_guard_descendant_initializers__ = True"] if source.constructor is not None else []),
                    *([f"    __svx_direct_mirror_field_ids__ = {physical_field_ids!r}"] if direct_receiver else []),
                    f"    __svx_projected_fields_by_class_id__ = {field_maps!r}",
                    "",
                    *subclass_registration,
                    "    def _svx_bind_active_projected_fields(self):",
                    "        # Project only fields selected for this concrete alternating-lineage target.",
                    "        declaration = getattr(type(self), '__svx_inheritance_class__', {})",
                    "        class_id = declaration.get('canonical_id') if isinstance(declaration, dict) else None",
                    f"        field_ids = {physical_field_ids!r}",
                    "        field_ids.update(self.__svx_projected_fields_by_class_id__.get(class_id, {}))",
                    "        if field_ids:",
                    "            self._svx_bind_projected_fields(field_ids)",
                    "",
                    "    @classmethod",
                    "    def __svx_create_from_sv__(cls, remote_object_id, *args):",
                    "        # Bind the existing SV instance before Python initialization reads projected fields.",
                    "        instance = cls.__new__(cls)",
                    "        SVMirror.__init__(instance)",
                    "        instance._svx_bind_remote_object(remote_object_id)",
                    "        bind_instance(remote_object_id, instance)",
                    "        try:",
                    "            instance._svx_bind_active_projected_fields()",
                    "            cls.__init__(instance, *args)",
                    "        except BaseException as initialization_error:",
                    "            SVMirror._svx_retire_failed_python_companion(instance, initialization_error)",
                    "            raise",
                    "        return instance",
                ]
            )
            if source.canonical_id in field_mirrors and source.constructor is None:
                lines.extend([
                    "", "    def __init__(self, remote_object_id: int):",
                    "        # Wrap an already registered endpoint; this path never allocates an SV object.",
                    "        SVMirror.__init__(self)",
                    "        self._svx_bind_remote_object(remote_object_id)",
                    "        bind_instance(remote_object_id, self)",
                    "        try:",
                    "            self._svx_bind_active_projected_fields()",
                    "        except BaseException as initialization_error:",
                    "            SVMirror._svx_retire_failed_python_companion(self, initialization_error)",
                    "            raise",
                ])
            else:
                direct_creator = _sv_generated_names(
                    {parameter.name for parameter in parameters} | set(scope.values()),
                    ('_create_sv_with_direct_mirror',),
                )['_create_sv_with_direct_mirror']
                natural_suspend = _sv_generated_names(
                    {parameter.name for parameter in parameters} | set(scope.values()),
                    ('_suspend_natural_constructor',),
                )['_suspend_natural_constructor']
                lines.extend([
                    "", f"    def __init__({signature}):",
                    *imports,
                    f"        from svx.inheritance import _suspend_natural_constructor as {natural_suspend}",
                    f"        if {natural_suspend}({owner}, {source.canonical_id!r}, {values}):",
                    "            return",
                    f"        if {owner}._svx_remote_object_id is not None:",
                    "            return",
                    # Do not traverse a preceding Python portion here. In an
                    # alternating class such as D(CMirror, B), B.__init__
                    # would reach AMirror and incorrectly allocate a second
                    # standalone A object. The generated mirror initializes
                    # only the common SvTypes/SVMirror base, then constructs
                    # its complete SV target below.
                    f"        {base}.__init__({owner})",
                    "        # Allocate the complete paired SV target for Python-initiated construction.",
                    *([
                        f"        from svx.inheritance import _create_sv_with_direct_mirror as {direct_creator}",
                        f"        {direct_creator}({owner}, {source.canonical_id!r}, {encode}({source.canonical_id!r}, {values}), {physical_field_ids!r})",
                    ] if direct_receiver else [
                    f"        {object_id} = {native}.inheritance_create_sv({source.canonical_id!r}, {encode}({source.canonical_id!r}, {values}))",
                    f"        {owner}._svx_bind_remote_object({object_id})",
                    "        try:",
                    f"            {bind}({object_id}, {owner})",
                    f"            {owner}._svx_bind_projected_fields({physical_field_ids!r})",
                    "        except BaseException:",
                    f"            {owner}._svx_release_projected_fields()",
                    f"            {native}.inheritance_close({object_id})",
                    "            raise",
                    f"        {owner}._svx_target_constructor_completed = True",
                    ]),
                ])
            for portion, method in surface_methods.values():
                lines.extend(_emit_python_bridge_method(method, portion.canonical_id))
            if not register_sv_subclasses:
                lines.extend(['', f'register_python_subclass({source.canonical_id!r}, {mirror_name})'])
            lines.append(f"_register_source_mirror_implementation({source.canonical_id!r}, {mirror_name})")
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"

    reverse_modules: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "python" and cls.canonical_id not in projected:
            reverse_modules.setdefault(_python_reverse_module_for(cls), []).append(cls)
    if reverse_modules:
        emitted[PurePosixPath("svx_py/__init__.py")] = _generated_python_init(
            manifest, "generated Python-to-SystemVerilog proxy package"
        )
    for module_name, classes in sorted(reverse_modules.items()):
        path = PurePosixPath(*module_name.split(".")).with_suffix(".py")
        lines = [
            *_generated_python_header(
                manifest,
                role="Python views of SystemVerilog-derived classes",
                targets=tuple(cls.canonical_id for cls in sorted(classes, key=lambda item: item.name)),
            ),
            "from __future__ import annotations",
            "from svx import _native",
            "from svx.inheritance import bind_instance, encode_constructor, invoke_sv, register_constructor, register_contract",
            *(["from svx.inheritance import invoke_sv_static, _register_python_static_methods"]
              if any(method.is_static for cls in classes for method in cls.methods) else []),
            "",
        ]
        for cls in sorted(classes, key=lambda item: item.name):
            source_module = ".".join(cls.symbol.split(".")[:-1])
            lines.extend([f"from {source_module} import {cls.name} as _Foreign{cls.name}", ""])
            lines.extend(_register_contract_lines(cls.methods))
            static_methods = tuple(method.canonical_id for method in cls.methods if method.is_static)
            if static_methods:
                lines.append(f"_register_python_static_methods({cls.canonical_id!r}, _Foreign{cls.name}, {static_methods!r})")
            if cls.constructor is not None:
                lines.append("# --- Construction contract ---")
                lines.append(
                    _constructor_registration(cls)
                )
            if (
                cls.constructor is not None
                and cls.constructor.initiator == "python"
            ):
                names = ", ".join(parameter.name for parameter in cls.constructor.parameters)
                scope, signature, imports = _python_constructor_scope(cls.constructor.parameters)
                owner, native, encode, bind = (scope[name] for name in ("self", "_native", "encode_constructor", "bind_instance"))
                foreign_name = f"_Foreign{cls.name}"
                foreign = _sv_generated_names({p.name for p in cls.constructor.parameters} | set(scope.values()), (foreign_name,))[foreign_name]
                if foreign != foreign_name:
                    imports.append(f"        from {source_module} import {cls.name} as {foreign}")
                constructor_values = "{" + ", ".join(
                    f"{parameter.name!r}: {parameter.name}"
                    for parameter in cls.constructor.parameters
                ) + "}"
                lines.extend([f"class {cls.name}(_Foreign{cls.name}):", f"    \"\"\"Python view of an SV-derived {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", f"    def __init__({signature}):", *imports, f"        {foreign}.__init__({owner}{', ' if names else ''}{names})", f"        {owner}._svx_remote_object_id = {native}.inheritance_create_sv({cls.canonical_id!r}, {encode}({cls.canonical_id!r}, {constructor_values}))", "        try:", f"            {bind}({owner}._svx_remote_object_id, {owner})", "        except BaseException:", f"            {native}.inheritance_close({owner}._svx_remote_object_id)", "            raise", "", "    def __svx_dispatch_foreign__(self, method_name: str, *args):", f"        return getattr(_Foreign{cls.name}, method_name)(self, *args)"])
            else:
                lines.extend([f"class {cls.name}(_Foreign{cls.name}):", f"    \"\"\"Python view of an SV-derived {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init__(self, remote_object_id: int):", "        self._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, self)", "", "    def __svx_dispatch_foreign__(self, method_name: str, *args):", f"        return getattr(_Foreign{cls.name}, method_name)(self, *args)"])
            for method in cls.methods:
                lines.extend(_emit_python_bridge_method(method, cls.canonical_id))
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"

    emitted.update(_emit_python_vif_views(manifest))
    return emitted


def _emit_python_vif_views(manifest: Manifest) -> dict[PurePosixPath, str]:
    """Emit restricted handle views independently of the logical root family."""
    emitted = {}
    vif_bindings = tuple(
        binding
        for binding in _manifest_handle_bindings(manifest)
        if binding.kind == "virtual_interface" and binding.collection_binding is None
    )
    if vif_bindings:
        emitted[PurePosixPath("svx_vif/__init__.py")] = _generated_python_init(
            manifest, "generated virtual-interface view package"
        )
    for binding in vif_bindings:
        parts = _vif_module_parts(binding)
        for depth in range(2, len(parts)):
            emitted.setdefault(
                PurePosixPath(*parts[:depth], "__init__.py"),
                _generated_python_init(manifest, "generated virtual-interface view package"),
            )
        path = PurePosixPath(*parts).with_suffix(".py")
        class_name = _vif_view_class_name(binding)
        lines = [
            *_generated_python_header(
                manifest,
                role="restricted Python view of a SystemVerilog virtual interface",
                targets=(binding.target_type_name,),
            ),
            "from __future__ import annotations",
            "from svx.inheritance import invoke_sv, register_contract, register_vif_view",
            "",
            *_register_contract_lines([operation.method for operation in binding.operations]),
            "",
        ]
        lines.extend(
            [
                f"class {class_name}:",
                f"    \"\"\"Generated restricted view of {binding.sv_type}.\"\"\"",
                f"    _svx_vif_target_type_name = {binding.target_type_name!r}",
                "",
                "    def __init__(self, reference):",
                "        if getattr(reference, 'target_type_name', None) != self._svx_vif_target_type_name:",
                "            raise TypeError('virtual-interface RemoteRef target does not match this view')",
                "        self._svx_remote_reference = reference",
                "        self._svx_remote_object_id = reference.object_number",
            ]
        )
        for operation in binding.operations:
            method = operation.method
            access = {
                "signal_read": "Read",
                "signal_write": "Write",
                "task": "Call task",
                "function": "Call function",
            }[operation.operation]
            lines.extend(
                [
                    "",
                    f"    # {access} access to {operation.sv_member_name!r} through {binding.sv_type}.",
                    *_emit_python_bridge_method(method)[1:],
                ]
            )
        lines.extend([
            "",
            "# Register this static target for inbound RemoteRef decoding.",
            f"register_vif_view({binding.target_type_name!r}, {class_name})",
            "",
        ])
        emitted[path] = "\n".join(lines)
    return emitted


def _sv_collection_typedef(binding: TypeBinding) -> tuple[str, str] | None:
    import svtypes

    codec = _codec_from_spec(binding.runtime_spec())
    if not isinstance(codec, (svtypes.Array, svtypes.DynArray, svtypes.AssocArray)):
        return None
    if binding.sv != svtypes.sv_type_expression(codec):
        return None  # Preserve an explicitly supplied source typedef.
    suffix = "".join(char if char.isascii() and char.isalnum() else f"_x{ord(char):x}_"
                     for char in binding.unified_type_name)
    name = "SVXValue_" + suffix
    return name, "typedef " + svtypes.sv_declaration(codec, name) + ";"


def _sv_value_type(binding: TypeBinding, *, qualified: bool = True) -> str:
    declaration = _sv_collection_typedef(binding)
    if declaration is None:
        return binding.sv
    return ("svx_call_records_pkg::" if qualified else "") + declaration[0]


def _sv_value_package_imports(classes) -> list[str]:
    packages = set()
    for source in classes:
        for declaration in (*source.base_lineage, source):
            bindings = [field.type_binding for field in declaration.fields]
            if declaration.constructor is not None:
                bindings.extend(parameter.type_binding for parameter in declaration.constructor.parameters)
            for method in declaration.methods:
                bindings.extend(parameter.type_binding for parameter in method.parameters)
                if method.return_type is not None:
                    bindings.append(method.return_type)
            for binding in bindings:
                if "::" in binding.sv:
                    package = binding.sv.split("::", 1)[0]
                    if package != "svtypes_pkg":
                        packages.add(package)
    return [f"  import {package}::*;" for package in sorted(packages)]


def _sv_parameters(method: Method, *, qualified: bool = True) -> str:
    if not method.parameters:
        return ""
    def render(parameter: Parameter) -> str:
        sv_type = _sv_handle_value_type(parameter.handle) if parameter.handle is not None else _sv_value_type(parameter.type_binding, qualified=qualified)
        return f"{parameter.direction} {sv_type} {parameter.name}"

    return ", ".join(render(parameter) for parameter in method.parameters)


def _sv_return_type(method: Method, *, qualified: bool = True) -> str:
    if method.return_type is None:
        return "void"
    return _sv_handle_value_type(method.return_handle) if method.return_handle is not None else _sv_value_type(method.return_type, qualified=qualified)


def _manifest_handle_bindings(manifest: Manifest) -> tuple[HandleBinding, ...]:
    """Return one compatible static endpoint description per RemoteRef target."""

    bindings: dict[str, HandleBinding] = {}

    def add(binding: HandleBinding) -> None:
        if binding.collection_binding is not None:
            add(replace(binding, collection_binding=None))
            bindings.setdefault(_handle_adapter_name(binding), replace(binding, operations=()))
            return
        previous = bindings.get(binding.target_type_name)
        if previous is None:
            bindings[binding.target_type_name] = binding
            return
        if (previous.kind, previous.sv_type) != (binding.kind, binding.sv_type):
            raise SVXInheritanceError(
                "one foreign handle target must have one static SV type: "
                f"{binding.target_type_name!r} is declared as both "
                f"{previous.sv_type!r} and {binding.sv_type!r}"
            )
        operations = {item.method.canonical_id: item for item in previous.operations}
        for item in binding.operations:
            existing = operations.setdefault(item.method.canonical_id, item)
            if existing != item:
                raise SVXInheritanceError(
                    "one virtual-interface operation must have one declaration: "
                    f"{item.method.canonical_id!r}"
                )
        bindings[binding.target_type_name] = HandleBinding(
            kind=previous.kind,
            target_type_name=previous.target_type_name,
            sv_type=previous.sv_type,
            operations=tuple(operations[key] for key in sorted(operations)),
        )

    for cls in _all_manifest_classes(manifest):
        for field in cls.fields:
            if field.handle is not None:
                add(field.handle)
        for parameter in (*((cls.constructor or Constructor("python", ())).parameters), *(
            parameter for method in cls.methods for parameter in method.parameters
        )):
            if parameter.handle is None:
                continue
            add(parameter.handle)
        for method in cls.methods:
            if method.return_handle is None:
                continue
            add(method.return_handle)
    return tuple(bindings[key] for key in sorted(bindings))


def _handle_adapter_name(binding: HandleBinding) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]", "_", binding.target_type_name).strip("_")
    if binding.collection_binding is not None:
        stem += "_" + "".join(char if char.isascii() and char.isalnum() else f"_x{ord(char):x}_"
                              for char in binding.collection_binding.unified_type_name)
    return "SVXExternal_" + stem


def _sv_handle_value_type(binding: HandleBinding) -> str:
    if binding.collection_binding is None:
        return binding.sv_type
    import svtypes
    value = binding.collection_binding
    codec = _codec_from_spec(value.runtime_spec())
    if value.sv != svtypes.sv_type_expression(codec):
        return value.sv
    return f"svx_external_handles_pkg::{_handle_adapter_name(binding)}::native_type"


def _handle_collection_shape(binding: HandleBinding):
    """Collect dimensions bottom-up for both native validation and conversion."""
    import svtypes

    codec = _codec_from_spec(binding.collection_binding.runtime_spec())
    nodes = []

    def collect(value):
        schema = svtypes.schema_descriptor(value).schema
        kind = schema['kind']
        if kind == 'remote_ref':
            return None
        if isinstance(value, svtypes.AssocArray):
            child = value.value_codec
            dimension = '[' + svtypes.sv_type_expression(value.key_codec) + ']'
        else:
            child = svtypes.FieldDescriptor(value).resolve_path(svtypes.FieldPath().index(0)).codec
            dimension = ('[$]' if isinstance(value, svtypes.Queue) else
                         '[]' if isinstance(value, svtypes.DynArray) else f"[{schema['size']}]")
        child_node = collect(child)
        node = (len(nodes), kind, dimension, child_node)
        nodes.append(node)
        return node

    root = collect(codec)
    return nodes, root


def _sv_native_handle_collection_typedefs(binding: HandleBinding, prefix: str):
    nodes, root = _handle_collection_shape(binding)
    declarations = []
    for index, _, dimension, child in nodes:
        native = binding.sv_type if child is None else f'{prefix}_{child[0]}'
        alias = f'{prefix}_{index}'
        declarations.append((alias, f'typedef {native} {alias}{dimension};'))
    return declarations, f'{prefix}_{root[0]}'


def _emit_sv_handle_collection_adapter(binding: HandleBinding, name: str) -> list[str]:
    """Convert a collection recursively while retaining scalar endpoint identity."""
    scalar = replace(binding, collection_binding=None)
    adapter = _handle_adapter_name(scalar)
    nodes, root = _handle_collection_shape(binding)
    native_typedefs, native_root = _sv_native_handle_collection_typedefs(binding, 'native')
    lines = [f'  class {name};']
    lines.extend('    ' + declaration for _, declaration in native_typedefs)
    for index, kind, dimension, child in nodes:
        wire = 'remote_ref' if child is None else f'wire_{child[0]}'
        lines.append(f'    typedef {wire} wire_{index}{dimension};')
    lines.extend([f'    typedef {native_root} native_type;',
                  f'    typedef wire_{root[0]} wire_type;'])

    def convert(node, source, target, decode, indent):
        if node is None:
            if decode:
                return [indent + f'if (!{adapter}::decode({source}, {target}, error)) return 0;']
            return [indent + f'{target} = {adapter}::encode({source});']
        index, kind, dimension, child = node
        result = []
        if kind == 'dyn_array':
            result.append(indent + f'{target} = new[{source}.size()];')
        elif kind in {'queue', 'assoc_array'}:
            result.append(indent + f'{target}.delete();')
        loop = f'index_{index}'
        result.append(indent + f'foreach ({source}[{loop}]) begin')
        if kind == 'queue':
            child_type = (binding.sv_type if decode else 'remote_ref') if child is None else (
                ('native_' if decode else 'wire_') + str(child[0]))
            temporary = f'element_{index}'
            result.append(indent + f'  {child_type} {temporary};')
            result.extend(convert(child, f'{source}[{loop}]', temporary, decode, indent + '  '))
            result.append(indent + f'  {target}.push_back({temporary});')
        else:
            result.extend(convert(child, f'{source}[{loop}]', f'{target}[{loop}]', decode, indent + '  '))
        result.append(indent + 'end')
        return result

    lines.extend(['    static function wire_type encode(input native_type value);',
                  '      wire_type converted;', *convert(root, 'value', 'converted', False, '      '),
                  '      return converted;', '    endfunction',
                  '    static function bit decode(input wire_type reference, output native_type value, output string error);',
                  '      native_type converted;', '      error = "";',
                  *convert(root, 'reference', 'converted', True, '      '),
                  '      value = converted;', '      return 1;', '    endfunction'])
    for node in nodes:
        index = node[0]
        lines.extend([f'    static function wire_{index} encode_{index}(input native_{index} value);',
                      f'      wire_{index} converted;',
                      *convert(node, 'value', 'converted', False, '      '),
                      '      return converted;', '    endfunction',
                      f'    static function bit decode_{index}(input wire_{index} reference, output native_{index} value, output string error);',
                      f'      native_{index} converted;', '      error = "";',
                      *convert(node, 'reference', 'converted', True, '      '),
                      '      value = converted;', '      return 1;', '    endfunction'])
    lines.append(f'  endclass : {name}')
    return lines


def _emit_sv_external_handle_adapters(manifest: Manifest, *,
                                      package_name: str | None = 'svx_external_handles_pkg',
                                      bindings: tuple[HandleBinding, ...] | None = None,
                                      adapter_names: Mapping[str, str] | None = None) -> list[str]:
    """Emit typed SV endpoints for every external class or VIF RemoteRef."""

    bindings = _manifest_handle_bindings(manifest) if bindings is None else bindings
    if not bindings:
        return []
    lines = [
        "",
        "// Private typed endpoints; RemoteRef is the sole encoded foreign-handle value.",
        *([f"package {package_name};"] if package_name is not None else []),
        "  import svx_pkg::*;",
        "  import svtypes_pkg::*;",
        "  import svx_call_records_pkg::*;",
    ]
    for binding in sorted(bindings, key=lambda item: item.collection_binding is not None):
        name = (adapter_names or {}).get(binding.target_type_name, _handle_adapter_name(binding))
        if binding.collection_binding is not None:
            lines.extend(_emit_sv_handle_collection_adapter(binding, _handle_adapter_name(binding)))
            continue
        target = json.dumps(binding.target_type_name)
        endpoint_interfaces = "svx_external_handle, svx_dispatchable, svx_function_dispatchable" if binding.operations else "svx_external_handle"
        lines.extend(
            [
                "",
                f"  // {binding.kind}: {binding.sv_type} <-> RemoteRef[{binding.target_type_name}].",
                f"  class {name}Endpoint implements {endpoint_interfaces};",
                f"    {binding.sv_type} value;",
                "    longint unsigned object_id;",
                "",
                f"    function new({binding.sv_type} value);",
                "      this.value = value;",
                "    endfunction",
                "",
                "    virtual function string svx_external_target_type();",
                f"      return {target};",
                "    endfunction",
            ]
        )
        if binding.operations:
            lines.extend(
                [
                    "",
                    "    virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
                    "      byte unsigned bytes[$];",
                    "      int offset;",
                    "      response = null;",
                    "      svx_payload_to_byte_queue(request, bytes);",
                    "      offset = 0;",
                    "      case (method_id)",
                ]
            )
            for operation in binding.operations:
                lines.extend(_emit_sv_vif_operation_dispatch_case(operation))
            lines.extend(
                [
                    "        default: begin",
                    "          ok = 0;",
                    "          error = {\"unsupported virtual-interface operation: \", method_id};",
                    "        end",
                    "      endcase",
                    "    endtask",
                ]
            )
            function_cases = [
                line
                for operation in binding.operations
                if operation.method.timing == "function"
                for line in _emit_sv_vif_operation_dispatch_case(operation)
            ]
            lines.extend(_emit_sv_function_invoker(function_cases))
        lines.extend(
            [
                f"  endclass : {name}Endpoint",
                "",
                f"  class {name} implements svx_session_resource;",
                f"    static {name}Endpoint endpoints[$];",
                f"    static {name} session_resource = new();",
                "",
                "    virtual function void clear_session();",
                "      endpoints.delete();",
                "    endfunction",
                "",
                f"    static function remote_ref encode({binding.sv_type} value);",
                "      longint unsigned object_id;",
                f"      {name}Endpoint endpoint;",
                "      remote_ref reference;",
                "      svx_external_handle_registry::register_resource(session_resource);",
                "      // Preserve the concrete SV handle in this session; encode only a typed RemoteRef.",
                f"      if (value == null) begin",
                f"        reference = new({target}, 0);",
                "        return reference;",
                "      end",
                "      foreach (endpoints[index]) begin",
                "        if (endpoints[index].value == value) begin",
                f"          reference = new({target}, endpoints[index].object_id);",
                "          return reference;",
                "        end",
                "      end",
                "      object_id = svx_external_handle_registry::allocate_object_id();",
                "      endpoint = new(value);",
                "      endpoint.object_id = object_id;",
                "      endpoints.push_back(endpoint);",
                "      svx_external_handle_registry::register_object(object_id, endpoint);",
                *(
                    ["      svx_inheritance_registry::register_object(object_id, endpoint);"]
                    if binding.operations
                    else []
                ),
                f"      reference = new({target}, object_id);",
                "      return reference;",
                "    endfunction",
                "",
                f"    static function bit decode(input remote_ref reference, output {binding.sv_type} value, output string error);",
                "      svx_external_handle raw;",
                f"      {name}Endpoint endpoint;",
                "      value = null;",
                "      error = \"\";",
                "      // Resolve this session-scoped RemoteRef back to the declared static SV type.",
                # RemoteRef's wire format carries only the ID. Collection
                # unpackers create untagged elements; the endpoint supplies
                # the static target and the registry still validates it.
                f'      if (reference != null && reference.target_type_name != "" && reference.target_type_name != {target}) begin',
                '        error = "external handle target mismatch";',
                "        return 0;",
                "      end",
                "      if (reference == null || reference.object_number == 0) return 1;",
                f"      if (!svx_external_handle_registry::resolve(reference.object_number, {target}, raw, error)) return 0;",
                "      if (!$cast(endpoint, raw)) begin",
                "        error = \"external handle registry returned an incompatible typed endpoint\";",
                "        return 0;",
                "      end",
                "      value = endpoint.value;",
                "      return 1;",
                "    endfunction",
                f"  endclass : {name}",
            ]
        )
    if package_name is not None:
        lines.extend([f"endpackage : {package_name}", ""])
    return lines


def _sv_record_type(
    owner_id: str,
    kind: str,
    fields: tuple[tuple[str, TypeBinding], ...],
):
    import svtypes

    schema_type = getattr(svtypes, "RecordSchema", None)
    if schema_type is None:
        raise SVXInheritanceError(
            "SvTypes 1.0 generated-call contract is unavailable: missing RecordSchema"
        )
    def record_codec(binding):
        codec = _codec_from_spec(binding.runtime_spec())
        if isinstance(codec, (svtypes.Array, svtypes.DynArray, svtypes.AssocArray)):
            # Transport envelopes do not define user coverage of handle values.
            try:
                _remote_ref_target(binding, 'generated call record')
            except SVXInheritanceError:
                pass
            else:
                identity = binding.runtime_spec().get('svtypes')
                if identity is not None:
                    declaration = svtypes.type_spec_from_identity(identity, location='generated call record')
                    codec = declaration(cov=False)
        return codec

    schema = schema_type(
        _call_record_type_id(owner_id, kind),
        tuple((name, record_codec(binding)) for name, binding in fields),
        class_name=_call_record_class_name(owner_id, kind),
    )
    value_type = schema.build()
    if value_type is None or not callable(getattr(value_type, "to_sv_obj", None)):
        raise SVXInheritanceError(
            f"SvTypes cannot generate the {kind} record for {owner_id}"
        )
    _validate_call_record_members(value_type, tuple(name for name, _ in fields), owner_id, kind)
    return value_type


def _validate_call_record_members(value_type: type, expected: tuple[str, ...], owner_id: str, kind: str):
    import svtypes

    descriptor = svtypes.schema_descriptor(value_type).to_dict()
    actual = tuple(field["name"] for field in descriptor["schema"]["fields"])
    if actual != expected:
        raise SVXInheritanceError(
            f"SvTypes {kind} record for {owner_id} does not preserve declared fields: "
            f"expected {expected!r}, got {actual!r}; the dependency must preserve "
            "explicit RecordSchema fields, including underscore-prefixed names"
        )


def _manifest_sv_record_types(manifest: Manifest) -> list[type]:
    records: list[type] = []
    for cls in _all_manifest_classes(manifest):
        if cls.constructor is not None and cls.constructor.parameters:
            records.append(
                _sv_record_type(
                    cls.canonical_id,
                    "request",
                    tuple(
                        (parameter.name, parameter.type_binding)
                        for parameter in cls.constructor.parameters
                    ),
                )
            )
        for method in cls.methods:
            request = tuple(
                (parameter.name, parameter.type_binding)
                for parameter in _request_parameters(method)
            )
            response = tuple(
                (parameter.name, parameter.type_binding)
                for parameter in _response_parameters(method)
            )
            if method.return_type is not None:
                response += ((_method_return_slot(method), method.return_type),)
            if request:
                records.append(_sv_record_type(method.canonical_id, "request", request))
            if response:
                records.append(_sv_record_type(method.canonical_id, "response", response))
    for binding in _manifest_handle_bindings(manifest):
        for operation in binding.operations:
            method = operation.method
            request = tuple(
                (parameter.name, parameter.type_binding)
                for parameter in _request_parameters(method)
            )
            response = tuple(
                (parameter.name, parameter.type_binding)
                for parameter in _response_parameters(method)
            )
            if method.return_type is not None:
                response += ((_method_return_slot(method), method.return_type),)
            if request:
                records.append(_sv_record_type(method.canonical_id, "request", request))
            if response:
                records.append(_sv_record_type(method.canonical_id, "response", response))
    return records


def _manifest_sv_collection_typedefs(manifest: Manifest) -> list[str]:
    bindings = []
    methods = []
    for cls in _all_manifest_classes(manifest):
        if cls.constructor is not None:
            bindings.extend(parameter.type_binding for parameter in cls.constructor.parameters
                            if parameter.handle is None)
        methods.extend(cls.methods)
    methods.extend(operation.method for handle in _manifest_handle_bindings(manifest)
                   for operation in handle.operations)
    for method in methods:
        bindings.extend(parameter.type_binding for parameter in method.parameters if parameter.handle is None)
        if method.return_type is not None and method.return_handle is None:
            bindings.append(method.return_type)
    declarations = {}
    for binding in bindings:
        declaration = _sv_collection_typedef(binding)
        if declaration is not None:
            name, text = declaration
            previous = declarations.setdefault(name, text)
            if previous != text:
                raise SVXInheritanceError(f"conflicting collection type declaration {name}")
    return [declarations[name] for name in sorted(declarations)]


def _sv_generated_names(occupied: set[str], requested: Iterable[str]) -> dict[str, str]:
    """Choose deterministic private names without changing public formals."""
    used = set(occupied)
    result = {}
    for name in requested:
        candidate = name
        suffix = 0
        while candidate in used:
            suffix += 1
            candidate = f"svx_{name}" if suffix == 1 else f"svx_{name}_{suffix - 1}"
        result[name] = candidate
        used.add(candidate)
    return result


def _emit_sv_outbound_method(method: Method, *, python_base: bool = False, python_static: bool = False,
                             callback_boundary: str | None = None, reserve_receiver: bool = False) -> list[str]:
    if python_static and (python_base or not method.is_static):
        raise SVXInheritanceError("Python static callback requires a static method and no instance base route")
    parameters = _sv_parameters(method)
    inputs = _request_parameters(method)
    outputs = _response_parameters(method)
    has_response = bool(outputs or method.return_type is not None)
    names = _sv_generated_names(
        {parameter.name for parameter in method.parameters} | {method.name},
        ("ok", "request", "response", "error", "bytes", "offset", "request_value", "response_value", "result"),
    )
    ok, request, response, error, data, offset, req, rsp, returned = names.values()
    prefix = _PYTHON_STATIC_METHOD_PREFIX if python_static else _PYTHON_BASE_METHOD_PREFIX if python_base else ""
    callback_id = prefix + method.canonical_id
    if callback_boundary is not None:
        if python_base or python_static:
            raise SVXInheritanceError('callback boundary cannot select a static or qualified-base route')
        callback_id = _PYTHON_CALLBACK_METHOD_PREFIX + json.dumps(
            {'boundary': callback_boundary, 'method': method.canonical_id}, separators=(',', ':'))
    receiver_id = "0" if python_static else "this.__svx_remote_object_id"
    qualifier = "static " if python_static else "" if python_base and not method.virtual else "virtual "
    header = (f"    {qualifier}task {method.name}({parameters});" if method.timing == "task"
              else f"    {qualifier}function {_sv_return_type(method)} {method.name}({parameters});")
    lines = ["", header, f"      bit {ok};", f"      chandle {request};",
             f"      chandle {response};", f"      string {error};", f"      byte unsigned {data}[$];"]
    if has_response:
        lines.append(f"      int {offset};")
    if inputs:
        lines.append(f"      {_call_record_class_name(method.canonical_id, 'request')} {req};")
    if has_response:
        lines.append(f"      {_call_record_class_name(method.canonical_id, 'response')} {rsp};")
    if method.return_type is not None:
        lines.append(f"      {_sv_return_type(method)} {returned};")
    if reserve_receiver and not python_static:
        lines.append("      this.__svx_reserve_early_receiver();")
    if inputs:
        lines.extend(["      // Pack declared input values through the generated SvTypes request record.",
                      f"      {req} = new();"])
        for parameter in inputs:
            value = parameter.name if parameter.handle is None else f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})"
            lines.append(f"      {req}.{parameter.name} = {value};")
        lines.append(f"      {req}.pack({data});")
    lines.extend([
        f'      {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
        "      // Cross the language boundary using this method's canonical ID.",
    ])
    if method.timing == "task":
        lines.append(f"      svx_inheritance_call_python({receiver_id}, {json.dumps(callback_id)}, {request}, {ok}, {response}, {error});")
    else:
        lines.append(f"      {response} = svx_inheritance_call_python_function({receiver_id}, {json.dumps(callback_id)}, {request}, {ok}, {error});")
    lines.extend([f"      svx_payload_destroy({request});", f"      if (!{ok}) begin",
                  f'        $fatal(2, "SVX inheritance callback {method.canonical_id} failed: %s", {error});', "      end"])
    if has_response:
        lines.extend([
            "      // Decode return and copy-out values from the generated SvTypes response record.",
            f"      if ({response} == null) begin",
            f'        $fatal(2, "SVX inheritance callback {method.canonical_id} returned no response");',
            "      end", f"      svx_payload_to_byte_queue({response}, {data});",
            f"      svx_payload_destroy({response});", f"      {offset} = 0;",
            f"      {rsp} = new();", f"      {rsp}.unpack({data}, {offset});",
        ])
        for parameter in outputs:
            if parameter.handle is None:
                lines.append(f"      {parameter.name} = {rsp}.{parameter.name};")
            else:
                lines.extend([
                    f"      if (!{_handle_adapter_name(parameter.handle)}::decode({rsp}.{parameter.name}, {parameter.name}, {error})) begin",
                    f'        $fatal(2, "SVX inheritance callback {method.canonical_id} returned invalid handle {parameter.name}: %s", {error});', "      end",
                ])
        if method.return_type is not None:
            if method.return_handle is None:
                lines.append(f"      {returned} = {rsp}.{_method_return_slot(method)};")
            else:
                lines.extend([
                    f"      if (!{_handle_adapter_name(method.return_handle)}::decode({rsp}.{_method_return_slot(method)}, {returned}, {error})) begin",
                    f'        $fatal(2, "SVX inheritance callback {method.canonical_id} returned invalid handle result: %s", {error});', "      end",
                ])
        lines.append(f'      svx_require_unpacked_all("{method.canonical_id}", "inheritance response", "call response", {offset}, {data}.size());')
    else:
        lines.extend([f"      if ({response} != null) begin", f"        svx_payload_destroy({response});", "      end"])
    if method.return_type is not None:
        lines.append(f"      return {returned};")
    lines.append("    endfunction" if method.timing == "function" else "    endtask")
    return lines


def _emit_sv_dispatch_case(method: Method, receiver: str = "") -> list[str]:
    if method.pure_virtual and receiver == "super.":
        # A concrete mirror implements the virtual callback, but its source
        # pure method still has no qualified base implementation to invoke.
        return [
            f"        {json.dumps(method.canonical_id)}: begin",
            "          ok = 0;",
            "          response = null;",
            '          error = $sformatf("SVX1|pure_virtual_base|%0d|%s|pure-virtual SV member has no base implementation", this.__svx_remote_object_id, method_id);',
            "        end",
        ]
    gateway = {"method_id", "request", "ok", "response", "error", "bytes", "offset"}
    inputs = _request_parameters(method)
    outputs = _response_parameters(method)
    names = _sv_generated_names(gateway | {p.name for p in method.parameters},
                               ("request_value", "response_value", "result"))
    req, rsp, returned = names.values()
    arguments = _sv_generated_names(gateway | set(names.values()) | {method.name},
                                    (p.name for p in method.parameters))
    lines = [f"        {json.dumps(method.canonical_id)}: begin",
             "          // Decode the typed request, invoke the declared target, then encode its response."]
    if inputs:
        lines.append(f"          {_call_record_class_name(method.canonical_id, 'request')} {req};")
    if outputs or method.return_type is not None:
        lines.append(f"          {_call_record_class_name(method.canonical_id, 'response')} {rsp};")
    for parameter in method.parameters:
        sv_type = _sv_handle_value_type(parameter.handle) if parameter.handle is not None else _sv_value_type(parameter.type_binding)
        lines.append(f"          {sv_type} {arguments[parameter.name]};")
    if method.return_type is not None:
        lines.append(f"          {_sv_return_type(method)} {returned};")
    if inputs:
        if any(parameter.handle is not None for parameter in inputs):
            lines.append("          // Foreign handles are resolved through typed RemoteRef endpoints.")
        lines.extend([f"          {req} = new();", f"          {req}.unpack(bytes, offset);"])
        for parameter in inputs:
            argument = arguments[parameter.name]
            if parameter.handle is None:
                lines.append(f"          {argument} = {req}.{parameter.name};")
            else:
                lines.extend([
                    f"          if (!{_handle_adapter_name(parameter.handle)}::decode({req}.{parameter.name}, {argument}, error)) begin",
                    "            ok = 0;", "            response = null;", "            return;", "          end",
                ])
    lines.append(f'          svx_require_unpacked_all("{method.canonical_id}", "inheritance request", "call request", offset, bytes.size());')
    values = ", ".join(arguments[p.name] for p in method.parameters)
    call = f"{receiver}{method.name}({values})"
    lines.append(f"          {call};" if method.return_type is None else f"          {returned} = {call};")
    lines.append("          bytes.delete();")
    if outputs or method.return_type is not None:
        lines.append(f"          {rsp} = new();")
        for parameter in outputs:
            value = arguments[parameter.name]
            if parameter.handle is not None:
                value = f"{_handle_adapter_name(parameter.handle)}::encode({value})"
            lines.append(f"          {rsp}.{parameter.name} = {value};")
        if method.return_type is not None:
            value = returned if method.return_handle is None else f"{_handle_adapter_name(method.return_handle)}::encode({returned})"
            lines.append(f"          {rsp}.{_method_return_slot(method)} = {value};")
        lines.append(f"          {rsp}.pack(bytes);")
    lines.extend(["          ok = 1;", '          error = "";',
                  '          response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
                  "        end"])
    return lines


def _emit_sv_vif_operation_dispatch_case(operation: VifOperation) -> list[str]:
    """Emit one typed VIF signal or subroutine operation on ``value``."""

    if operation.operation in {"task", "function"}:
        # Subroutine argument names are user-controlled and may themselves be
        # called ``value``.  Qualify the endpoint field to avoid shadowing it.
        return _emit_sv_dispatch_case(operation.method, receiver="this.value.")

    method = operation.method
    result = [f"        {json.dumps(method.canonical_id)}: begin"]
    if operation.operation == "signal_read":
        assert method.return_type is not None
        result.extend(
            [
                f"          {method.return_type.sv} result;",
                f"          {_call_record_class_name(method.canonical_id, 'response')} response_value;",
                "          if (bytes.size() != 0) begin",
                "            ok = 0;",
                '            error = "VIF signal read request must be empty";',
                "            response = null;",
                "            return;",
                "          end",
                f"          result = value.{operation.sv_member_name};",
                "          bytes.delete();",
                "          response_value = new();",
                f"          response_value.{_method_return_slot(method)} = result;",
                "          response_value.pack(bytes);",
                "          ok = 1;",
                '          error = "";',
                '          response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
                "        end",
            ]
        )
        return result

    assert operation.operation == "signal_write"
    parameter = method.parameters[0]
    result.extend(
        [
            f"          {_call_record_class_name(method.canonical_id, 'request')} request_value;",
            f"          {parameter.type_binding.sv} value_to_write;",
            "          request_value = new();",
            "          request_value.unpack(bytes, offset);",
            f"          value_to_write = request_value.{parameter.name};",
            f'          svx_require_unpacked_all("{method.canonical_id}", "VIF signal write", "call request", offset, bytes.size());',
            f"          value.{operation.sv_member_name} = value_to_write;",
            "          bytes.delete();",
            "          ok = 1;",
            '          error = "";',
            '          response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
            "        end",
        ]
    )
    return result


def _emit_sv_field_dispatch_cases(cls: ForeignClass, field: Field) -> list[str]:
    import svtypes

    if field.handle is not None and field.handle.collection_binding is None:
        return _emit_sv_handle_field_dispatch_cases(cls, field)
    codec = _codec_from_spec(field.type_binding.runtime_spec())
    context = getattr(svtypes, 'sv_codegen_context', None)
    if not callable(context):
        raise SVXInheritanceError('field bridge generation requires public SvTypes sv_codegen_context()')
    with context(codec, prefix='__svx_field_' + field.name) as declarations:
        lines = _emit_sv_value_field_dispatch_cases(cls, field)
    if not declarations:
        return lines
    result = []
    for line in lines:
        result.append(line)
        if line.startswith('        "') and line.endswith(': begin'):
            result.extend('          ' + declaration for declaration in declarations)
    return result


def _emit_sv_value_field_dispatch_cases(cls: ForeignClass, field: Field) -> list[str]:
    """Emit root read/set endpoints used only by ``SVXFieldStorage``.

    SvTypes owns byte normalization and descriptor checking on the Python side;
    generated SV code owns the matching concrete packer and rejects trailing
    bytes. Path-aware collection endpoints are added with their explicit
    manifest operation table rather than silently doing whole-field writeback.
    """

    if field.handle is not None:
        return _emit_sv_handle_field_dispatch_cases(cls, field)
    field_id = f"{cls.canonical_id}.{field.name}"
    import svtypes
    packer = svtypes.sv_packer_expression(_codec_from_spec(field.type_binding.runtime_spec()))
    lines = [
        f"        {json.dumps(field_id + '@svx_field_read')}: begin",
        "          if (bytes.size() != 0) begin",
        "            ok = 0;",
        '            error = "field read request must be empty";',
        "          end else begin",
        "            bytes.delete();",
        f"            {packer}::pack(this.{field.name}, bytes);",
        "            ok = 1;",
        '            error = "";',
        '            response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
        "          end",
        "        end",
        f"        {json.dumps(field_id + '@svx_field_set')}: begin",
        "          int field_offset;",
        "          field_offset = 0;",
        f"          {packer}::unpack(this.{field.name}, bytes, field_offset);",
        f'          svx_require_unpacked_all("{field_id}", "field write", "field value", field_offset, bytes.size());',
        "          bytes.delete();",
        "          ok = 1;",
        '          error = "";',
        '          response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
        "        end",
    ]
    lines.extend(_emit_sv_field_operation_case(cls, field))
    return lines


def _emit_sv_handle_field_dispatch_cases(cls: ForeignClass, field: Field) -> list[str]:
    """Keep native handle members separate from their SvTypes wire values."""

    assert field.handle is not None
    field_id = f"{cls.canonical_id}.{field.name}"
    adapter = _handle_adapter_name(field.handle)
    import svtypes
    packer = svtypes.sv_packer_expression(_codec_from_spec(field.type_binding.runtime_spec()))
    wire_type = (f'{adapter}::wire_type' if field.handle.collection_binding is not None
                 else field.type_binding.sv)
    read = [
        f"{wire_type} field_wire;",
        f"field_wire = {adapter}::encode(this.{field.name});",
        "bytes.delete();",
        f"{packer}::pack(field_wire, bytes);",
        *_emit_sv_field_operation_success(),
    ]

    def write(payload: str) -> list[str]:
        return [
            f"{wire_type} field_wire;",
            f"{_sv_handle_value_type(field.handle)} field_native;",
            "int field_offset;",
            *([] if field.handle.collection_binding is not None else
              [f"field_wire = new({json.dumps(field.handle.target_type_name)});"]),
            "field_offset = 0;",
            f"{packer}::unpack(field_wire, {payload}, field_offset);",
            f'svx_require_unpacked_all("{field_id}", "field write", "field value", field_offset, {payload}.size());',
            f"if (!{adapter}::decode(field_wire, field_native, error)) begin",
            "  ok = 0;",
            "  response = null;",
            "end else begin",
            f"  this.{field.name} = field_native;",
            "  bytes.delete();",
            *["  " + line for line in _emit_sv_field_operation_success()],
            "end",
        ]

    lines = [f"        {json.dumps(field_id + '@svx_field_read')}: begin",
             "          if (bytes.size() != 0) begin",
             '            ok = 0; error = "field read request must be empty";',
             "          end else begin", *["            " + line for line in read],
             "          end", "        end",
             f"        {json.dumps(field_id + '@svx_field_set')}: begin",
             *["          " + line for line in write("bytes")], "        end",
             f"        {json.dumps(field_id + '@svx_field_operation')}: begin",
             "          svx_field_operation operation;",
             "          int field_offset;",
             "          if (!svx_field_operation_unpack(bytes, operation, error)) begin",
             "            ok = 0;"]
    if field.handle.collection_binding is not None:
        codec = _codec_from_spec(field.type_binding.runtime_spec())
        _, root = _handle_collection_shape(field.handle)
        lines.extend(["          end else begin", "            bytes.delete();",
                      *('            ' + line for line in _emit_sv_deep_handle_field_access(
                          field.handle, codec, root, f'this.{field.name}', field_id)),
                      "          end", "        end"])
        return lines
    lines.extend([
             "          end else if (operation.path_kind.size() != 0) begin",
             '            ok = 0; error = "field path extends a handle value";',
             "          end else if (operation.code == 0) begin",
             *["            " + line for line in read],
             "          end else if (operation.code == 1 && operation.has_payload) begin",
             *["            " + line for line in write("operation.payload")],
             "          end else begin",
             '            ok = 0; error = "unsupported handle field operation";',
             "          end", "        end"])
    return lines


def _emit_sv_handle_sequence_mutation(binding, codec, node, expression, field_id, depth, *, indexed):
    import svtypes

    child = node[3]
    child_codec = svtypes.FieldDescriptor(codec).resolve_path(svtypes.FieldPath().index(0)).codec
    adapter = _handle_adapter_name(binding if child is not None else replace(binding, collection_binding=None))
    native = f'{adapter}::native_{child[0]}' if child is not None else binding.sv_type
    wire = f'{adapter}::wire_{child[0]}' if child is not None else 'remote_ref'
    suffix = f'_{child[0]}' if child is not None else ''
    packer = svtypes.sv_packer_expression(child_codec)
    queue = isinstance(codec, svtypes.Queue)
    index = f'operation.path_index[{depth}]'
    size = f'{expression}.size()'
    success = [line.strip() for line in _emit_sv_field_operation_success()]
    condition = (f'operation.code == 2 && operation.has_payload && {index} <= {size}'
                 if indexed else 'operation.code == 4 && operation.has_payload')
    lines = [f'if ({condition}) begin', f'  {wire} field_wire;',
             f'  {native} field_element;']
    if child is None:
        lines.append(f'  field_wire = new({json.dumps(binding.target_type_name)});')
    lines.extend(['  field_offset = 0;',
                  f'  {packer}::unpack(field_wire, operation.payload, field_offset);',
                  f'  svx_require_unpacked_all("{field_id}", "field insertion", "field element", field_offset, operation.payload.size());',
                  f'  if (!{adapter}::decode{suffix}(field_wire, field_element, error)) begin',
                  '    ok = 0; response = null;', '  end else begin'])
    if queue:
        if indexed:
            lines.extend([f'    if ({index} == {size}) {expression}.push_back(field_element);',
                          f'    else {expression}.insert({index}, field_element);'])
        else:
            lines.append(f'    {expression}.push_back(field_element);')
    else:
        lines.append(f'    {native} field_sequence[];')
        if indexed:
            lines.extend([f'    field_sequence = new[{size} + 1];',
                          f'    for (int i = 0; i < {index}; i++) field_sequence[i] = {expression}[i];',
                          f'    field_sequence[{index}] = field_element;',
                          f'    for (int i = {index}; i < {size}; i++) field_sequence[i + 1] = {expression}[i];'])
        else:
            lines.extend([f'    field_sequence = new[{size} + 1]({expression});',
                          f'    field_sequence[{size}] = field_element;'])
        lines.append(f'    {expression} = field_sequence;')
    lines.extend([*('    ' + line for line in success), '  end', 'end'])
    if indexed:
        lines.append(f'else if ((operation.code == 3 || operation.code == 5) && {index} < {size}) begin')
        if queue:
            lines.append(f'  {expression}.delete({index});')
        else:
            lines.extend([f'  {native} field_sequence[];',
                          f'  field_sequence = new[{size} - 1];',
                          f'  for (int i = 0; i < {index}; i++) field_sequence[i] = {expression}[i];',
                          f'  for (int i = {index} + 1; i < {size}; i++) field_sequence[i - 1] = {expression}[i];',
                          f'  {expression} = field_sequence;'])
        lines.extend([*('  ' + line for line in success), 'end'])
    else:
        lines.extend(['else if (operation.code == 6 && operation.has_payload) begin',
                      '  int field_length;', f'  {native} field_default;',
                      '  field_offset = 0;',
                      f'  {svtypes.sv_packer_expression(svtypes.Int())}::unpack(field_length, operation.payload, field_offset);',
                      f'  svx_require_unpacked_all("{field_id}", "field resize", "field length", field_offset, operation.payload.size());',
                      '  if (field_length < 0) begin',
                      '    ok = 0; error = "field resize requires nonnegative length";',
                      '  end else begin'])
        if queue:
            lines.extend([f'    while ({size} > field_length) {expression}.delete({size} - 1);',
                          f'    while ({size} < field_length) {expression}.push_back(field_default);'])
        else:
            lines.append(f'    {expression} = new[field_length]({expression});')
        lines.extend([*('    ' + line for line in success), '  end', 'end'])
    lines.extend(['else begin', '  ok = 0; error = "unsupported or out-of-range handle sequence mutation";', 'end'])
    return lines


def _emit_sv_deep_handle_field_access(binding, codec, node, expression, field_id, depth=0):
    """Convert only the addressed native handle value, never its parent."""
    import svtypes

    with svtypes.sv_codegen_context(codec, prefix=f'__svx_handle_path_{depth}') as declarations:
        packer = svtypes.sv_packer_expression(codec)
        adapter = _handle_adapter_name(binding if node is not None else
                                       replace(binding, collection_binding=None))
        wire = f'{adapter}::wire_{node[0]}' if node is not None else 'remote_ref'
        native = f'{adapter}::native_{node[0]}' if node is not None else binding.sv_type
        suffix = f'_{node[0]}' if node is not None else ''
        success = [line.strip() for line in _emit_sv_field_operation_success()]
        lines = [f'if (operation.path_kind.size() == {depth}) begin',
                 '  if (operation.code == 0) begin', f'    {wire} field_wire;',
                 f'    field_wire = {adapter}::encode{suffix}({expression});',
                 f'    {packer}::pack(field_wire, bytes);',
                 *('    ' + line for line in success),
                 '  end else if (operation.code == 1 && operation.has_payload) begin',
                 f'    {wire} field_wire;', f'    {native} field_native;']
        if node is None:
            lines.append(f'    field_wire = new({json.dumps(binding.target_type_name)});')
        lines.extend(['    field_offset = 0;',
                      f'    {packer}::unpack(field_wire, operation.payload, field_offset);',
                      f'    svx_require_unpacked_all("{field_id}", "field write", "field leaf", field_offset, operation.payload.size());',
                      f'    if (!{adapter}::decode{suffix}(field_wire, field_native, error)) begin',
                      '      ok = 0; response = null;', '    end else begin',
                      f'      {expression} = field_native;',
                      *('      ' + line for line in success), '    end', '  end'])
        if isinstance(codec, (svtypes.DynArray, svtypes.Queue)):
            lines.append('  else begin')
            lines.extend('    ' + line for line in _emit_sv_handle_sequence_mutation(
                binding, codec, node, expression, field_id, depth, indexed=False))
            lines.append('  end')
        else:
            lines.extend(['  else begin', '    ok = 0; error = "unsupported handle field operation";', '  end'])
        lines.append('end else begin')
        if node is None:
            lines.append('  ok = 0; error = "field path extends a handle value";')
        else:
            child = node[3]
            if isinstance(codec, svtypes.AssocArray):
                child_codec = codec.value_codec
                key = f'field_key_{depth}'
                child_expression = f'{expression}[{key}]'
                lines.extend([f'  if (operation.path_kind[{depth}] == 3) begin',
                              f'    {svtypes.sv_type_expression(codec.key_codec)} {key};',
                              '    field_offset = 0;',
                              f'    {svtypes.sv_packer_expression(codec.key_codec)}::unpack({key}, operation.path_key[{depth}], field_offset);',
                              f'    svx_require_unpacked_all("{field_id}", "field key", "field key", field_offset, operation.path_key[{depth}].size());',
                              f'    if (!{expression}.exists({key}) && !(operation.path_kind.size() == {depth + 1} && operation.code == 1 && operation.has_payload)) begin',
                              '      ok = 0; error = "missing associative field key";',
                              f'    end else if (operation.path_kind.size() == {depth + 1} && (operation.code == 3 || operation.code == 5)) begin',
                              f'      {expression}.delete({key});',
                              *('      ' + line for line in success),
                              '    end else begin'])
                child_lines = _emit_sv_deep_handle_field_access(
                    binding, child_codec, child, child_expression, field_id, depth + 1)
                lines.extend('      ' + line for line in child_lines)
                lines.extend(['    end', '  end else begin',
                              '    ok = 0; error = "unsupported handle field key path";', '  end'])
            else:
                child_codec = svtypes.FieldDescriptor(codec).resolve_path(svtypes.FieldPath().index(0)).codec
                size = f'$size({expression})' if isinstance(codec, svtypes.Array) else f'{expression}.size()'
                index = f'operation.path_index[{depth}]'
                if isinstance(codec, (svtypes.DynArray, svtypes.Queue)):
                    lines.append(f'  if (operation.path_kind.size() == {depth + 1} && operation.path_kind[{depth}] == 2 && (operation.code == 2 || operation.code == 3 || operation.code == 5)) begin')
                    lines.extend('    ' + line for line in _emit_sv_handle_sequence_mutation(
                        binding, codec, node, expression, field_id, depth, indexed=True))
                    lines.append(f'  end else if (operation.path_kind[{depth}] == 2 && {index} < {size}) begin')
                else:
                    lines.append(f'  if (operation.path_kind[{depth}] == 2 && {index} < {size}) begin')
                lines.extend('    ' + line for line in _emit_sv_deep_handle_field_access(
                    binding, child_codec, child, f'{expression}[{index}]', field_id, depth + 1))
                lines.extend(['  end else begin',
                              '    ok = 0; error = "unsupported or out-of-range handle field index";', '  end'])
        lines.append('end')
    if declarations:
        return ['begin', *('  ' + line for line in declarations),
                *('  ' + line for line in lines), 'end']
    return lines


def _field_operation_profile(binding: TypeBinding) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Return generated-SV reflection needed for one public SvTypes field.

    The manifest gives the root declaration directly.  Child lvalues are only
    needed for addressed external storage operations, so resolve them from the
    same concrete SvTypes codec used to validate the manifest's descriptor.
    """

    try:
        import svtypes
        from svtypes import Array, AssocArray, DynArray, Queue

        codec = _codec_from_spec(binding.runtime_spec())
        if isinstance(codec, (Queue, DynArray, Array)):
            element = svtypes.FieldDescriptor(codec).resolve_path(
                svtypes.FieldPath().index(0)
            ).codec
            return (
                "queue" if isinstance(codec, Queue) else
                "dyn_array" if isinstance(codec, DynArray) else "fixed_array",
                svtypes.sv_type_expression(element),
                svtypes.sv_packer_expression(element),
                None,
                None,
            )
        if isinstance(codec, AssocArray):
            identity = binding.runtime_spec().get("svtypes")
            if identity is not None:
                annotation = svtypes.type_spec_from_identity(
                    identity, location="SVX associative field"
                )
                key, value = (
                    svtypes.materialize_type_spec(argument, location="SVX associative field argument")
                    for argument in annotation.parameters
                )
                return (
                    "assoc_array",
                    svtypes.sv_type_expression(value),
                    svtypes.sv_packer_expression(value),
                    svtypes.sv_type_expression(key),
                    svtypes.sv_packer_expression(key),
                )
            # Custom factories expose their concrete codecs through SvTypes.
            return (
                "assoc_array",
                svtypes.sv_type_expression(codec.value_codec),
                svtypes.sv_packer_expression(codec.value_codec),
                svtypes.sv_type_expression(codec.key_codec),
                svtypes.sv_packer_expression(codec.key_codec),
            )
    except (ImportError, AttributeError, NotImplementedError) as error:
        raise SVXInheritanceError(
            f"cannot generate addressed field operations for {binding.unified_type_name}"
        ) from error
    return ("scalar", None, None, None, None)


def _emit_sv_field_operation_success() -> list[str]:
    return [
        "            ok = 1;",
        '            error = "";',
        '            response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
    ]


def _emit_sv_sequence_mutation(codec: Any, expression: str, field_id: str,
                               depth: int, *, indexed: bool) -> list[str]:
    import svtypes

    child = svtypes.FieldDescriptor(codec).resolve_path(svtypes.FieldPath().index(0)).codec
    child_type = svtypes.sv_type_expression(child)
    child_packer = svtypes.sv_packer_expression(child)
    queue = isinstance(codec, svtypes.Queue)
    index = f"operation.path_index[{depth}]"
    size = f"{expression}.size()"
    success = [line.strip() for line in _emit_sv_field_operation_success()]
    if not indexed:
        lines = ["else if (operation.code == 4 && operation.has_payload) begin",
                 f"  {child_type} field_element;", "  field_offset = 0;",
                 f"  {child_packer}::unpack(field_element, operation.payload, field_offset);",
                 f'  svx_require_unpacked_all("{field_id}", "field append", "field element", field_offset, operation.payload.size());']
        if queue:
            lines.append(f"  {expression}.push_back(field_element);")
        else:
            # Declare the temporary in a separate block before any statements.
            lines.extend(["  begin", f"    {child_type} field_sequence[];",
                          f"    field_sequence = new[{size} + 1]({expression});",
                          f"    field_sequence[{size}] = field_element;",
                          f"    {expression} = field_sequence;", "  end"])
        lines.extend([*("  " + line for line in success), "end",
                      "else if (operation.code == 6 && operation.has_payload) begin",
                      "  int field_length;", f"  {child_type} field_default;",
                      "  field_offset = 0;",
                      f"  {svtypes.sv_packer_expression(svtypes.Int())}::unpack(field_length, operation.payload, field_offset);",
                      f'  svx_require_unpacked_all("{field_id}", "field resize", "field length", field_offset, operation.payload.size());',
                      "  if (field_length < 0) begin",
                      '    ok = 0; error = "field resize requires nonnegative length";',
                      "  end else begin"])
        if queue:
            lines.extend([f"    while ({size} > field_length) {expression}.delete({size} - 1);",
                          f"    while ({size} < field_length) {expression}.push_back(field_default);"])
        else:
            lines.append(f"    {expression} = new[field_length]({expression});")
        lines.extend([*("    " + line for line in success), "  end", "end"])
        return lines
    lines = [f"if (operation.code == 2 && operation.has_payload && {index} <= {size}) begin",
             f"  {child_type} field_element;", "  field_offset = 0;",
             f"  {child_packer}::unpack(field_element, operation.payload, field_offset);",
             f'  svx_require_unpacked_all("{field_id}", "field insert", "field element", field_offset, operation.payload.size());']
    if queue:
        lines.extend([f"  if ({index} == {size}) {expression}.push_back(field_element);",
                      f"  else {expression}.insert({index}, field_element);"])
    else:
        lines.extend(["  begin", f"    {child_type} field_sequence[];",
                      f"    field_sequence = new[{size} + 1];",
                      f"    for (int i = 0; i < {index}; i++) field_sequence[i] = {expression}[i];",
                      f"    field_sequence[{index}] = field_element;",
                      f"    for (int i = {index}; i < {size}; i++) field_sequence[i + 1] = {expression}[i];",
                      f"    {expression} = field_sequence;", "  end"])
    lines.extend([*("  " + line for line in success), "end",
                  f"else if ((operation.code == 3 || operation.code == 5) && {index} < {size}) begin"])
    if queue:
        lines.append(f"  {expression}.delete({index});")
    else:
        lines.extend([f"  {child_type} field_sequence[];",
                      f"  field_sequence = new[{size} - 1];",
                      f"  for (int i = 0; i < {index}; i++) field_sequence[i] = {expression}[i];",
                      f"  for (int i = {index} + 1; i < {size}; i++) field_sequence[i - 1] = {expression}[i];",
                      f"  {expression} = field_sequence;"])
    lines.extend([*("  " + line for line in success), "end else begin",
                  '  ok = 0; error = "unsupported or out-of-range sequence mutation";', "end"])
    return lines


def _emit_sv_deep_field_access(codec: Any, expression: str, field_id: str,
                               depth: int = 0, ancestors: tuple[str, ...] = ()) -> list[str]:
    """Resolve a typed path to an SV lvalue without copying its parent value."""
    import svtypes

    with svtypes.sv_codegen_context(codec, prefix=f'__svx_path_{depth}') as declarations:
        lines = _emit_sv_deep_field_access_body(codec, expression, field_id, depth, ancestors)
    if declarations:
        return ['begin', *('  ' + line for line in declarations),
                *('  ' + line for line in lines), 'end']
    return lines


def _emit_sv_deep_field_access_body(codec: Any, expression: str, field_id: str,
                                    depth: int, ancestors: tuple[str, ...]) -> list[str]:
    import svtypes
    from svtypes import Array, AssocArray, DynArray, Queue

    descriptor = svtypes.FieldDescriptor(codec)
    packer = svtypes.sv_packer_expression(codec)
    lines = [f"if (operation.path_kind.size() == {depth}) begin",
             "  if (operation.code == 0) begin",
             f"    {packer}::pack({expression}, bytes);",
             *["    " + line.strip() for line in _emit_sv_field_operation_success()],
             "  end else if (operation.code == 1 && operation.has_payload) begin",
             "    field_offset = 0;",
             f"    {packer}::unpack({expression}, operation.payload, field_offset);",
             f'    svx_require_unpacked_all("{field_id}", "field write", "field leaf", field_offset, operation.payload.size());',
             *["    " + line.strip() for line in _emit_sv_field_operation_success()],
             "  end"]
    if isinstance(codec, (DynArray, Queue)):
        lines.extend("  " + line for line in _emit_sv_sequence_mutation(
            codec, expression, field_id, depth, indexed=False))
    lines.extend(["  else begin",
             '    ok = 0; error = "unsupported deep field operation or missing payload";',
             "  end"])
    if isinstance(codec, (DynArray, Queue)):
        lines.extend([f"end else if (operation.path_kind.size() == {depth + 1} &&",
                      f"             operation.path_kind[{depth}] == 2 &&",
                      "             (operation.code == 2 || operation.code == 3 || operation.code == 5)) begin",
                      *["  " + line for line in _emit_sv_sequence_mutation(
                          codec, expression, field_id, depth, indexed=True)]])
    lines.append("end else begin")
    children = []
    identity = descriptor.unified_type_name
    if identity not in ancestors:
        if isinstance(codec, (Array, DynArray, Queue)):
            child = descriptor.resolve_path(svtypes.FieldPath().index(0)).codec
            size = f"$size({expression})" if isinstance(codec, Array) else f"{expression}.size()"
            condition = (f"operation.path_kind[{depth}] == 2 && "
                         f"operation.path_index[{depth}] < {size}")
            children.append((condition, [], child, f"{expression}[operation.path_index[{depth}]]"))
        elif isinstance(codec, AssocArray):
            key = f"field_key_{depth}"
            setup = [f"{svtypes.sv_type_expression(codec.key_codec)} {key};",
                     "field_offset = 0;",
                     f"{svtypes.sv_packer_expression(codec.key_codec)}::unpack({key}, operation.path_key[{depth}], field_offset);",
                     f' svx_require_unpacked_all("{field_id}", "field key", "field key", field_offset, operation.path_key[{depth}].size());']
            children.append((f"operation.path_kind[{depth}] == 3", setup,
                             codec.value_codec, f"{expression}[{key}]"))
        else:
            schema = descriptor.schema_descriptor.schema
            if schema.get("kind") == "object_ref":
                target = codec.registry.get(codec.cls_name)
                if target is None:
                    raise SVXInheritanceError(f"field object type {identity} is not registered")
                schema = svtypes.schema_descriptor(target).schema
            if schema.get("kind") in {"object", "struct"}:
                for member in schema.get("fields", ()):
                    name = member["name"]
                    child = descriptor.resolve_path(svtypes.FieldPath().member(name)).codec
                    condition = f"operation.path_kind[{depth}] == 1 && operation.path_member[{depth}] == {json.dumps(name)}"
                    if schema["kind"] == "object":
                        condition += f" && {expression} != null"
                    children.append((condition, [], child, f"{expression}.{name}"))
    for index, (condition, setup, child, child_expression) in enumerate(children):
        lines.append(f"  {'if' if index == 0 else 'else if'} ({condition}) begin")
        lines.extend("    " + line for line in setup)
        child_lines = _emit_sv_deep_field_access(child, child_expression, field_id,
                                                depth + 1, (*ancestors, identity))
        if isinstance(codec, AssocArray):
            lines.extend([f"    if (operation.path_kind.size() == {depth + 1} && operation.code == 1 && operation.has_payload) begin",
                          *["      " + line for line in child_lines],
                          f"    end else if (!{expression}.exists(field_key_{depth})) begin",
                          '      ok = 0; error = "missing associative field key";',
                          f"    end else if (operation.path_kind.size() == {depth + 1} && (operation.code == 3 || operation.code == 5)) begin",
                          f"      {expression}.delete(field_key_{depth});",
                          *["      " + line.strip() for line in _emit_sv_field_operation_success()],
                          "    end else begin"])
            lines.extend("      " + line for line in child_lines)
            lines.append("    end")
        else:
            lines.extend("    " + line for line in child_lines)
        lines.append("  end")
    lines.extend(["  else begin" if children else "  begin",
                  '    ok = 0; error = "unsupported or out-of-range deep field path";',
                  "  end", "end"])
    return lines


def _emit_sv_field_operation_case(cls: ForeignClass, field: Field) -> list[str]:
    """Emit addressed SvTypes field operations without whole-field writeback."""

    field_id = f"{cls.canonical_id}.{field.name}"
    import svtypes
    root_packer = svtypes.sv_packer_expression(_codec_from_spec(field.type_binding.runtime_spec()))
    kind, element_type, element_packer, key_type, key_packer = _field_operation_profile(
        field.type_binding
    )
    size_expression = (
        f"$size(this.{field.name})" if kind == "fixed_array" else f"this.{field.name}.size()"
    )
    lines = [
        f"        {json.dumps(field_id + '@svx_field_operation')}: begin",
        "          svx_field_operation operation;",
        "          int field_offset;",
        "          if (!svx_field_operation_unpack(bytes, operation, error)) begin",
        "            ok = 0;",
        "          end else if (operation.code == 6 || (operation.code >= 2 && operation.path_kind.size() != 0) ||",
        "                       operation.path_kind.size() > 1 ||",
        "                       (operation.path_kind.size() == 1 && operation.path_kind[0] == 1)) begin",
        "            bytes.delete();",
        *["            " + line for line in _emit_sv_deep_field_access(
            _codec_from_spec(field.type_binding.runtime_spec()), f"this.{field.name}", field_id)],
        "          end else begin",
        "            bytes.delete();",
        "            case (operation.code)",
        "              0: begin",  # read
        "                if (operation.path_kind.size() == 0) begin",
        f"                  {root_packer}::pack(this.{field.name}, bytes);",
        *["                  " + line.strip() for line in _emit_sv_field_operation_success()],
        "                end",
    ]
    if kind in {"queue", "dyn_array", "fixed_array"}:
        assert element_packer is not None
        lines.extend(
            [
                "                else if (operation.path_kind.size() == 1 && operation.path_kind[0] == 2 &&",
                f"                         operation.path_index[0] < {size_expression}) begin",
                f"                  {element_packer}::pack(this.{field.name}[operation.path_index[0]], bytes);",
                *["                  " + line.strip() for line in _emit_sv_field_operation_success()],
                "                end else begin",
                "                  ok = 0;",
                '                  error = "unsupported or out-of-range indexed field read";',
                "                end",
            ]
        )
    elif kind == "assoc_array":
        assert key_type is not None and key_packer is not None and element_packer is not None
        lines.extend(
            [
                "                else if (operation.path_kind.size() == 1 && operation.path_kind[0] == 3) begin",
                f"                  {key_type} field_key;",
                "                  field_offset = 0;",
                f"                  {key_packer}::unpack(field_key, operation.path_key[0], field_offset);",
                f'                  svx_require_unpacked_all("{field_id}", "field key", "field key", field_offset, operation.path_key[0].size());',
                f"                  if (!this.{field.name}.exists(field_key)) begin",
                "                    ok = 0;",
                '                    error = "missing associative field key";',
                "                  end else begin",
                f"                    {element_packer}::pack(this.{field.name}[field_key], bytes);",
                *["                    " + line.strip() for line in _emit_sv_field_operation_success()],
                "                  end",
                "                end else begin",
                "                  ok = 0;",
                '                  error = "unsupported associative field read";',
                "                end",
            ]
        )
    else:
        lines.extend(
            [
                "                else begin",
                "                  ok = 0;",
                '                  error = "field path extends a scalar value";',
                "                end",
            ]
        )

    lines.extend(
        [
            "              end",
            "              1: begin",  # set
            "                if (!operation.has_payload) begin",
            "                  ok = 0;",
            '                  error = "field set requires payload bytes";',
            "                end else if (operation.path_kind.size() == 0) begin",
            "                  field_offset = 0;",
            f"                  {root_packer}::unpack(this.{field.name}, operation.payload, field_offset);",
            f'                  svx_require_unpacked_all("{field_id}", "field write", "field value", field_offset, operation.payload.size());',
            *["                  " + line.strip() for line in _emit_sv_field_operation_success()],
            "                end",
        ]
    )
    if kind in {"queue", "dyn_array", "fixed_array"}:
        assert element_packer is not None and element_type is not None
        lines.extend(
            [
                "                else if (operation.path_kind.size() == 1 && operation.path_kind[0] == 2 &&",
                f"                         operation.path_index[0] < {size_expression}) begin",
                f"                  {element_type} field_value;",
                "                  field_offset = 0;",
                f"                  {element_packer}::unpack(field_value, operation.payload, field_offset);",
                f'                  svx_require_unpacked_all("{field_id}", "field write", "field element", field_offset, operation.payload.size());',
                f"                  this.{field.name}[operation.path_index[0]] = field_value;",
                *["                  " + line.strip() for line in _emit_sv_field_operation_success()],
                "                end else begin",
                "                  ok = 0;",
                '                  error = "unsupported or out-of-range indexed field write";',
                "                end",
            ]
        )
    elif kind == "assoc_array":
        assert key_type is not None and key_packer is not None and element_type is not None and element_packer is not None
        lines.extend(
            [
                "                else if (operation.path_kind.size() == 1 && operation.path_kind[0] == 3) begin",
                f"                  {key_type} field_key;",
                f"                  {element_type} field_value;",
                "                  field_offset = 0;",
                f"                  {key_packer}::unpack(field_key, operation.path_key[0], field_offset);",
                f'                  svx_require_unpacked_all("{field_id}", "field key", "field key", field_offset, operation.path_key[0].size());',
                "                  field_offset = 0;",
                f"                  {element_packer}::unpack(field_value, operation.payload, field_offset);",
                f'                  svx_require_unpacked_all("{field_id}", "field write", "field value", field_offset, operation.payload.size());',
                f"                  this.{field.name}[field_key] = field_value;",
                *["                  " + line.strip() for line in _emit_sv_field_operation_success()],
                "                end else begin",
                "                  ok = 0;",
                '                  error = "unsupported associative field write";',
                "                end",
            ]
        )
    else:
        lines.extend(
            [
                "                else begin",
                "                  ok = 0;",
                '                  error = "field path extends a scalar value";',
                "                end",
            ]
        )
    lines.extend(["              end"])

    if kind in {"queue", "dyn_array"}:
        assert element_type is not None and element_packer is not None
        lines.extend(
            [
                "              2, 4: begin",  # insert, append
                "                if (!operation.has_payload) begin",
                "                  ok = 0;",
                '                  error = "sequence insertion requires payload bytes";',
                "                end else begin",
                f"                  {element_type} field_value;",
                "                  field_offset = 0;",
                f"                  {element_packer}::unpack(field_value, operation.payload, field_offset);",
                f'                  svx_require_unpacked_all("{field_id}", "field update", "field element", field_offset, operation.payload.size());',
                "                  if (operation.code == 4 && operation.path_kind.size() == 0) begin",
            ]
        )
        if kind == "queue":
            lines.append(f"                    this.{field.name}.push_back(field_value);")
        else:
            lines.extend(
                [
                    f"                    {element_type} field_resize[];",
                    f"                    field_resize = new[this.{field.name}.size() + 1](this.{field.name});",
                    f"                    field_resize[this.{field.name}.size()] = field_value;",
                    f"                    this.{field.name} = field_resize;",
                ]
            )
        lines.extend(
            [
                *["                    " + line.strip() for line in _emit_sv_field_operation_success()],
                "                  end else if (operation.code == 2 && operation.path_kind.size() == 1 &&",
                f"                               operation.path_kind[0] == 2 && operation.path_index[0] <= this.{field.name}.size()) begin",
            ]
        )
        if kind == "queue":
            lines.append(f"                    this.{field.name}.insert(operation.path_index[0], field_value);")
        else:
            lines.extend(
                [
                    f"                    {element_type} field_insert[];",
                    f"                    field_insert = new[this.{field.name}.size() + 1];",
                    f"                    for (int i = 0; i < operation.path_index[0]; i++) field_insert[i] = this.{field.name}[i];",
                    "                    field_insert[operation.path_index[0]] = field_value;",
                    f"                    for (int i = operation.path_index[0]; i < this.{field.name}.size(); i++) field_insert[i + 1] = this.{field.name}[i];",
                    f"                    this.{field.name} = field_insert;",
                ]
            )
        lines.extend(
            [
                *["                    " + line.strip() for line in _emit_sv_field_operation_success()],
                "                  end else begin",
                "                    ok = 0;",
                '                    error = "unsupported sequence insertion path";',
                "                  end",
                "                end",
                "              end",
                "              3, 5: begin",  # delete, pop
                "                if (operation.path_kind.size() != 1 || operation.path_kind[0] != 2 ||",
                f"                    operation.path_index[0] >= this.{field.name}.size()) begin",
                "                  ok = 0;",
                '                  error = "unsupported or out-of-range sequence removal";',
                "                end else begin",
            ]
        )
        if kind == "queue":
            lines.append(f"                  this.{field.name}.delete(operation.path_index[0]);")
        else:
            lines.extend(
                [
                    f"                  {element_type} field_delete[];",
                    f"                  field_delete = new[this.{field.name}.size() - 1];",
                    f"                  for (int i = 0; i < operation.path_index[0]; i++) field_delete[i] = this.{field.name}[i];",
                    f"                  for (int i = operation.path_index[0] + 1; i < this.{field.name}.size(); i++) field_delete[i - 1] = this.{field.name}[i];",
                    f"                  this.{field.name} = field_delete;",
                ]
            )
        lines.extend([*["                  " + line.strip() for line in _emit_sv_field_operation_success()], "                end", "              end"])

    if kind == "assoc_array":
        assert key_type is not None and key_packer is not None
        lines.extend(
            [
                "              3, 5: begin",
                "                if (operation.path_kind.size() != 1 || operation.path_kind[0] != 3) begin",
                "                  ok = 0;",
                '                  error = "associative removal requires a key path";',
                "                end else begin",
                f"                  {key_type} field_key;",
                "                  field_offset = 0;",
                f"                  {key_packer}::unpack(field_key, operation.path_key[0], field_offset);",
                f'                  svx_require_unpacked_all("{field_id}", "field key", "field key", field_offset, operation.path_key[0].size());',
                f"                  if (!this.{field.name}.exists(field_key)) begin",
                "                    ok = 0;",
                '                    error = "missing associative field key";',
                "                  end else begin",
                f"                    this.{field.name}.delete(field_key);",
                *["                    " + line.strip() for line in _emit_sv_field_operation_success()],
                "                  end",
                "                end",
                "              end",
            ]
        )

    lines.extend(
        [
            "              default: begin",
            "                ok = 0;",
            '                error = "unsupported projected-field operation";',
            "              end",
            "            endcase",
            "          end",
            "        end",
        ]
    )
    return lines


def _emit_sv_function_invoker(
    cases: list[str], *, static: bool = False, delegate: bool = False
) -> list[str]:
    name = "svx_invoke_static_function" if static else "svx_invoke_function"
    qualifier = "static" if static else "virtual"
    lines = [
        "",
        f"    {qualifier} function void {name}(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
        "      byte unsigned bytes[$];",
        "      int offset;",
        "      response = null;",
        "      svx_payload_to_byte_queue(request, bytes);",
        "      offset = 0;",
        "      case (method_id)",
        *cases,
    ]
    if delegate:
        lines.append(f"        default: super.{name}(method_id, request, ok, response, error);")
    else:
        lines.extend([
            "        default: begin",
            "          ok = 0;",
            '          error = {"member is not available as a function: ", method_id};',
            "        end",
        ])
    lines.extend(["      endcase", "    endfunction"])
    return lines


def _emit_sv_projection_invoke(
    cls: ForeignClass,
    *,
    base_methods: tuple[Method, ...],
    delegate_unmatched_to_super: bool = False,
    inherited_sv_sources: tuple[ForeignClass, ...] = (),
) -> list[str]:
    """Emit generated base gateways and selected projected-field endpoints."""

    lines = [
        "",
        "    virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
        "      byte unsigned bytes[$];",
        "      int offset;",
        "      response = null;",
        "      svx_payload_to_byte_queue(request, bytes);",
        "      offset = 0;",
        "      case (method_id)",
    ]
    for method in base_methods:
        lines.extend(_emit_sv_dispatch_case(method, "super."))
    for source in inherited_sv_sources:
        for method in source.methods:
            if not method.is_static:
                lines.extend(_emit_sv_dispatch_case(method, _sv_class_reference(source) + '::'))
        for field in source.fields:
            lines.extend(_emit_sv_field_dispatch_cases(source, field))
    for field in cls.fields:
        lines.extend(_emit_sv_field_dispatch_cases(cls, field))
    if delegate_unmatched_to_super:
        # A Python-to-SV proxy sits above an SV mirror.  Its inherited member
        # calls must reach the mirror's explicit base gateway, rather than
        # invoking the mirror's virtual override and re-entering Python.
        lines.extend(
            [
                "        // Delegate inherited base calls to the explicit gateway; avoid re-entering a virtual Python override.",
                "        default: super.svx_invoke(method_id, request, ok, response, error);",
                "      endcase",
                "    endtask",
            ]
        )
    else:
        lines.extend(
            [
                "        default: begin",
                "          ok = 0;",
                '          error = {"unsupported projected member: ", method_id};',
                "        end",
                "      endcase",
                "    endtask",
            ]
        )
    function_cases = [
        line for method in base_methods if method.timing == "function"
        for line in _emit_sv_dispatch_case(method, "super.")
    ]
    for source in inherited_sv_sources:
        function_cases.extend(line for method in source.methods if method.timing == 'function' and not method.is_static
                              for line in _emit_sv_dispatch_case(method, _sv_class_reference(source) + '::'))
        for field in source.fields:
            function_cases.extend(_emit_sv_field_dispatch_cases(source, field))
    for field in cls.fields:
        function_cases.extend(_emit_sv_field_dispatch_cases(cls, field))
    lines.extend(_emit_sv_function_invoker(
        function_cases, delegate=delegate_unmatched_to_super
    ))
    return lines


def _emit_sv_natural_constructor_wrappers(generated_name: str, python_source: ForeignClass,
                                          sv_source: ForeignClass) -> tuple[list[str], dict[str, str]]:
    """Capture one Python portion's evaluated super arguments per paired ID."""
    if python_source.language != "python" or sv_source.language != "sv":
        raise SVXInheritanceError("natural constructor wrappers require a Python-to-SV boundary")
    parameters = python_source.constructor.parameters if python_source.constructor else ()
    base_parameters = sv_source.constructor.parameters if sv_source.constructor else ()
    names = _sv_generated_names({p.name for p in (*parameters, *base_parameters)}, (
        "object_id", "arguments", "prepare_id", "resume", "captured", "prepared",
        "request_value", "result", "request", "response", "bytes", "ok", "error", "offset",
        "cleanup_instance",
        *("argument_" + p.name for p in base_parameters),
    ))
    oid, capture, prepared = (names[key] for key in ("object_id", "captured", "prepared"))
    args = ", ".join([f"input longint unsigned {oid}", *(
        f"input {_sv_handle_value_type(p.handle) if p.handle else _sv_value_type(p.type_binding)} {p.name}"
        for p in parameters)])
    values = ", ".join([oid, *(p.name for p in parameters)])
    base_record = _call_record_class_name(sv_source.canonical_id, "request")
    python_record = _call_record_class_name(python_source.canonical_id, "request")
    request_value, result, request, response, data, ok, error, offset = (
        names[key] for key in ("request_value", "result", "request", "response", "bytes", "ok", "error", "offset"))
    def route(phase):
        return json.dumps(_NATURAL_CONSTRUCTOR_PREFIX + json.dumps(
            {"phase": phase, "python": python_source.canonical_id, "sv": sv_source.canonical_id},
            separators=(",", ":")))
    lines = ["", f"  // Original {python_source.canonical_id} initializer -> {sv_source.canonical_id} super arguments.",
             f"  class {generated_name} extends svx_constructor_cache;",
             f"    static {generated_name} {names['cleanup_instance']};",
             f"    static bit {prepared}[longint unsigned];"]
    if base_parameters:
        lines.append(f"    static {base_record} {capture}[longint unsigned];")
    lines.extend([
        "    virtual function void retire_receiver(longint unsigned receiver_id);",
        f"      {prepared}.delete(receiver_id);",
        *([f"      {capture}.delete(receiver_id);"] if base_parameters else []),
        "    endfunction",
    ])
    lines.extend([f"    static function void {names['arguments']}({args});",
                  f"      chandle {request}, {response};", f"      byte unsigned {data}[$];",
                  f"      bit {ok};", f"      string {error};"])
    if parameters:
        lines.append(f"      {python_record} {request_value};")
    if base_parameters:
        lines.extend([f"      {base_record} {result};", f"      int {offset};"])
    lines.append(f"      if ({prepared}.exists({oid})) return;")
    lines.extend([
        f"      if ({names['cleanup_instance']} == null) begin",
        f"        {names['cleanup_instance']} = new();",
        f"        svx_constructor_cache_registry::register_cache({names['cleanup_instance']});",
        "      end",
    ])
    if parameters:
        lines.append(f"      {request_value} = new();")
        for p in parameters:
            value = f"{_handle_adapter_name(p.handle)}::encode({p.name})" if p.handle else p.name
            lines.append(f"      {request_value}.{p.name} = {value};")
        lines.append(f"      {request_value}.pack({data});")
    lines.extend([
        f'      {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
        f"      {response} = svx_inheritance_call_python_function({oid}, {route('prepare')}, {request}, {ok}, {error});",
        f"      svx_payload_destroy({request});",
        f"      if (!{ok} || {response} == null) begin",
        f"        if ({response} != null) svx_payload_destroy({response});",
        f"        svx_construction_context::retire_id({oid});",
        f"        svx_inheritance_registry::unbind({oid});",
        f'        $fatal(2, "SVX natural constructor preparation failed: %s", {error});',
        "      end",
        f"      svx_payload_to_byte_queue({response}, {data});", f"      svx_payload_destroy({response});",
    ])
    if base_parameters:
        lines.extend([f"      {result} = new();", f"      {offset} = 0;",
                      f"      {result}.unpack({data}, {offset});",
                      f'      if ({offset} != {data}.size()) $fatal(2, "SVX natural constructor arguments have trailing bytes");',
                      f"      {capture}[{oid}] = {result};"])
    else:
        lines.append(f'      if ({data}.size() != 0) $fatal(2, "SVX empty super constructor received arguments");')
    lines.extend([f"      {prepared}[{oid}] = 1;", "    endfunction"])
    for p in base_parameters:
        native_type = _sv_handle_value_type(p.handle) if p.handle else _sv_value_type(p.type_binding)
        lines.extend([f"    static function {native_type} {names['argument_' + p.name]}({args});"])
        if p.handle:
            lines.extend([f"      {native_type} {result};", f"      string {error};"])
        lines.append(f"      {names['arguments']}({values});")
        if p.handle:
            lines.extend([
                f"      if (!{_handle_adapter_name(p.handle)}::decode({capture}[{oid}].{p.name}, {result}, {error}))",
                f'        $fatal(2, "SVX natural constructor handle decoding failed: %s", {error});',
                f"      return {result};"])
        else:
            lines.append(f"      return {capture}[{oid}].{p.name};")
        lines.append("    endfunction")
    lines.extend([f"    static function longint unsigned {names['prepare_id']}({args});",
                  f"      {names['arguments']}({values});", f"      return {oid};", "    endfunction",
                  f"    static function void {names['resume']}(input longint unsigned {oid});",
                  f"      chandle {response};", f"      bit {ok};", f"      string {error};",
                  f"      {response} = svx_inheritance_call_python_function({oid}, {route('resume')}, null, {ok}, {error});",
                  f"      if ({response} != null) svx_payload_destroy({response});",
                  f"      if (!{ok}) begin",
                  f"        {prepared}.delete({oid});",
                  *([f"        {capture}.delete({oid});"] if base_parameters else []),
                  f"        svx_construction_context::retire_id({oid});",
                  f"        svx_inheritance_registry::unbind({oid});",
                  f'        $fatal(2, "SVX natural constructor resumption failed: %s", {error});',
                  "      end",
                  f"      {prepared}.delete({oid});"])
    if base_parameters:
        lines.append(f"      {capture}.delete({oid});")
    lines.extend(["    endfunction", "  endclass"])
    return lines, names


def _emit_sv_projection_class(
    generated_name: str,
    base_type: str | None,
    cls: ForeignClass,
    *,
    base_methods: tuple[Method, ...],
    dispatch_virtuals: tuple[Method, ...],
    delegate_unmatched_to_super: bool = False,
    constructor_source: ForeignClass | None = None,
    reuse_base_object_id: bool = False,
    super_accepts_object_id: bool = False,
    is_root_sv_mirror: bool = False,
    is_root_python_proxy: bool = False,
    staged_python_root: ForeignClass | None = None,
    staged_sv_root: ForeignClass | None = None,
    constructor_python_portions: tuple[ForeignClass, ...] | None = None,
    transparent_construction: bool = False,
    callback_boundary: str | None = None,
    dynamic_sv_root: bool = False,
    early_receiver_binding: bool = False,
    inherited_sv_sources: tuple[ForeignClass, ...] = (),
    deferred_python_constructor: ForeignClass | None = None,
    natural_constructor_base: ForeignClass | None = None,
) -> list[str]:
    """Emit an AMirror or BProxy portion without manufacturing user classes."""

    if base_type is None and not is_root_python_proxy:
        raise SVXInheritanceError("a projection without an SV base requires a Python-root constructor")
    if is_root_python_proxy and (base_type is not None or cls.language != "python"):
        raise SVXInheritanceError("Python-root projection must have a Python source and no fabricated SV ancestor")
    if staged_python_root is not None and (not reuse_base_object_id
                                          or staged_python_root.language != "python"):
        raise SVXInheritanceError("staged Python portion requires a Python root and a reused paired ID")
    if staged_sv_root is not None and (not is_root_sv_mirror or staged_sv_root.language != "python"):
        raise SVXInheritanceError("staged SV root requires a root mirror and its first Python portion")
    natural_wrappers: list[str] = []
    natural_names: dict[str, str] = {}
    natural_helper = generated_name + "_constructor_arguments"
    reserve_natural_receiver = natural_constructor_base is not None and staged_python_root is not None
    if natural_constructor_base is not None:
        if (cls.language != "python" or natural_constructor_base.language != "sv"
                or not reuse_base_object_id or not super_accepts_object_id
                or constructor_source is not None or transparent_construction):
            raise SVXInheritanceError("natural proxy constructor requires a Python portion and paired SV mirror base")
        natural_wrappers, natural_names = _emit_sv_natural_constructor_wrappers(
            natural_helper, cls, natural_constructor_base)
    extends = f" extends {base_type}" if base_type is not None else ""
    lines = [
        *natural_wrappers,
        "",
        f"  // Generated {'AMirror' if cls.language == 'sv' else 'BProxy'} for {cls.canonical_id}.",
        f"  class {generated_name}{extends} implements svx_dispatchable, svx_function_dispatchable;",
    ]
    context_constructor = constructor_source.constructor if constructor_source is not None else cls.constructor
    context_occupied = {field.name for owner in (cls, *inherited_sv_sources) for field in owner.fields}
    context_occupied.update(parameter.name for parameter in (
        context_constructor.parameters if context_constructor is not None else ()))
    context_occupied.update(method.name for owner in (cls, *inherited_sv_sources) for method in owner.methods)
    context_occupied.update(parameter.name for owner in (cls, *inherited_sv_sources)
                            for method in owner.methods for parameter in method.parameters)
    context_type = _sv_generated_names(context_occupied, ('__svx_construction_context_type',))[
        '__svx_construction_context_type']
    if transparent_construction or early_receiver_binding or reserve_natural_receiver:
        lines.append(f"    typedef svx_pkg::svx_construction_context {context_type};")
    if not reuse_base_object_id:
        lines.append("    longint unsigned __svx_remote_object_id;")
    if deferred_python_constructor is not None:
        lines.extend(["", "    virtual function bit __svx_defer_python_constructor();",
                      f"      return {1 if cls.language == 'python' else 0};", "    endfunction"])
    if cls.fields and cls.language == "python":
        lines.append("    // Projected fields are accessed by Python through the SvTypes external-storage bridge.")
        for field in cls.fields:
            lines.append(f"    {_sv_field_declaration(field)};")
    if is_root_python_proxy or staged_python_root is not None:
        root_id = cls.canonical_id if is_root_python_proxy else staged_python_root.canonical_id
        portions = constructor_python_portions if constructor_python_portions is not None else (() if is_root_python_proxy else (cls,))
        if any(portion.language != "python" for portion in portions):
            raise SVXInheritanceError("constructor portions must identify Python source initializers")
        selector = _PYTHON_ROOT_ALLOC_PREFIX + json.dumps({"root": root_id, "target": cls.canonical_id,
                                                        "portions": [portion.canonical_id for portion in portions]}, separators=(",", ":"))
        lines.extend(["", "    virtual function string __svx_python_constructor_target();",
                      f"      return {json.dumps(selector)};", "    endfunction"])
    elif staged_sv_root is not None or dynamic_sv_root:
        lines.extend(["", "    virtual function string __svx_python_constructor_target();",
                      f"      return {json.dumps(cls.canonical_id)};", "    endfunction"])
    if transparent_construction and (is_root_sv_mirror and dynamic_sv_root or is_root_python_proxy):
        lines.extend([
            "", "    function void __svx_reserve_early_receiver();",
            "      bit ok;", "      string error;", "      chandle request;",
            "      byte unsigned bytes[$];",
            "      if (this.__svx_remote_object_id != 0) return;",
            f"      this.__svx_remote_object_id = {context_type}::current_id(this);",
            "      if (this.__svx_remote_object_id == 0)",
            "        this.__svx_remote_object_id = svx_inheritance_registry::allocate_object_id();",
            f"      {context_type}::bind_id(this, this.__svx_remote_object_id);",
            "      svx_inheritance_registry::register_object(this.__svx_remote_object_id, this);",
            '      request = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
            f"      ok = svx_inheritance_create_python_function({{{json.dumps(_PYTHON_RECEIVER_RESERVE_PREFIX)}, this.__svx_python_constructor_target()}}, this.__svx_remote_object_id, request, error);",
            "      svx_payload_destroy(request);",
            "      if (!ok) begin",
            "        svx_inheritance_registry::unbind(this.__svx_remote_object_id);",
            '        $fatal(2, "SVX early receiver reservation failed: %s", error);',
            "      end", "    endfunction",
        ])
    constructor = constructor_source.constructor if constructor_source is not None else cls.constructor
    constructor_names = _sv_generated_names(
        {p.name for p in constructor.parameters} if constructor is not None else set(),
        ("object_id", "ok", "request", "error", "bytes", "request_value"),
    )
    object_id, ok, request, error, data, record = constructor_names.values()
    natural_reservation_names = _sv_generated_names(
        context_occupied | set(constructor_names.values()),
        ("__svx_prepare_natural_receiver", "receiver_prepared"),
    )
    if reserve_natural_receiver:
        prepare_receiver = natural_reservation_names["__svx_prepare_natural_receiver"]
        lines.extend([
            "", f"    function bit {prepare_receiver}(input longint unsigned {object_id});",
            f"      if ({object_id} != 0) {context_type}::bind_id(this, {object_id});",
            "      this.__svx_reserve_early_receiver();",
            "      return 1;", "    endfunction",
        ])
    defer_sv_root = is_root_sv_mirror and dynamic_sv_root and transparent_construction
    root_initialization_selector = (
        f'{{{json.dumps(_PYTHON_ROOT_INIT_PREFIX)}, this.__svx_python_constructor_target()}}'
        if dynamic_sv_root else json.dumps(_PYTHON_ROOT_INIT_PREFIX + (
            staged_sv_root.canonical_id if staged_sv_root is not None else cls.canonical_id)))
    scope_owned = _sv_generated_names(
        set(constructor_names.values()) | {parameter.name for parameter in (constructor.parameters if constructor is not None else ())},
        ('scope_owned',),
    )['scope_owned']
    constructor_parameters = (
        ", ".join(f"input {_sv_handle_value_type(p.handle) if p.handle is not None else _sv_value_type(p.type_binding)} {p.name}" for p in constructor.parameters)
        if constructor is not None
        else ""
    )
    constructor_arguments = (
        ", ".join(p.name for p in constructor.parameters) if constructor is not None else ""
    )
    constructor_parameters_with_optional_id = ", ".join(
        item
        for item in (
            constructor_parameters,
            f"input longint unsigned {object_id} = " + (
                "svx_inheritance_registry::allocate_object_id()"
                if natural_constructor_base is not None and not reserve_natural_receiver else "0"),
        )
        if item
    )
    # Argument defaults establish the receiver frame before base construction.
    owns_construction_scope = reserve_natural_receiver or transparent_construction and (
        is_root_sv_mirror or is_root_python_proxy or (
            reuse_base_object_id and not (staged_python_root is not None and cls.language == 'python'))
    )
    if owns_construction_scope:
        constructor_parameters_with_optional_id += (
            f", input bit {scope_owned} = {context_type}::enter({object_id}, this)"
        )
    if reserve_natural_receiver:
        constructor_parameters_with_optional_id += (
            f", input bit {natural_reservation_names['receiver_prepared']} = "
            f"{natural_reservation_names['__svx_prepare_natural_receiver']}({object_id})"
        )
    constructor_arguments_with_id = ", ".join(
        item for item in (constructor_arguments, object_id) if item
    )
    if natural_constructor_base is not None:
        receiver_id = "this.__svx_remote_object_id" if reserve_natural_receiver else object_id
        inputs = ", ".join(item for item in (receiver_id, constructor_arguments) if item)
        base_parameters = (natural_constructor_base.constructor.parameters
                           if natural_constructor_base.constructor is not None else ())
        super_arguments = [
            f"{natural_helper}::{natural_names['argument_' + parameter.name]}({inputs})"
            for parameter in base_parameters
        ]
        super_arguments.append(f"{natural_helper}::{natural_names['prepare_id']}({inputs})")
        lines.extend([
            "", f"    function new({constructor_parameters_with_optional_id});",
            f"      super.new({', '.join(super_arguments)});",
            f"      {natural_helper}::{natural_names['resume']}(this.__svx_remote_object_id);",
            *([f"      {context_type}::leave(this, {scope_owned});"] if owns_construction_scope else []),
            "    endfunction",
        ])
    elif is_root_sv_mirror or is_root_python_proxy:
        lines.extend(
            [
                "",
                f"    function new({constructor_parameters_with_optional_id});",
                f"      bit {ok};",
                f"      chandle {request};",
                f"      string {error};",
                f"      byte unsigned {data}[$];",
                *(
                    [
                        f"      {_call_record_class_name(cls.canonical_id, 'request')} {record};"
                    ]
                    if constructor is not None and constructor.parameters
                    else []
                ),
                *([f"      super.new({constructor_arguments});"] if base_type is not None else []),
                *([f"      {object_id} = {context_type}::current_id(this);"] if transparent_construction else []),
                *([
                    "      // Reserve now; the first Python proxy initializes after its field declarations.",
                    f"      if (this.__svx_python_constructor_target().substr(0, {len(_PYTHON_ROOT_ALLOC_PREFIX) - 1}) == {json.dumps(_PYTHON_ROOT_ALLOC_PREFIX)}) begin",
                    "        this.__svx_reserve_early_receiver();",
                    "      end else begin",
                ] if defer_sv_root else []),
                f"      if ({object_id} == 0) begin",
                "        // SV owns construction: allocate and bind the object ID before entering Python.",
                "        this.__svx_remote_object_id = svx_inheritance_registry::allocate_object_id();",
                "        svx_inheritance_registry::register_object(this.__svx_remote_object_id, this);",
                *(["        if (!this.__svx_defer_python_constructor()) begin"]
                  if deferred_python_constructor is not None else []),
            ]
        )
        if constructor is not None and constructor.parameters:
            lines.append(f"        {record} = new();")
            for parameter in constructor.parameters:
                value = f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})" if parameter.handle is not None else parameter.name
                lines.append(f"        {record}.{parameter.name} = {value};")
            lines.append(f"        {record}.pack({data});")
        lines.extend(
            [
                f'        {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
                f"        {ok} = svx_inheritance_create_python_function({'this.__svx_python_constructor_target()' if is_root_python_proxy or staged_sv_root is not None or dynamic_sv_root else json.dumps(cls.canonical_id)}, this.__svx_remote_object_id, {request}, {error});",
                f"        svx_payload_destroy({request});",
                f"        if (!{ok}) begin",
                "          svx_inheritance_registry::unbind(this.__svx_remote_object_id);",
                f'          $fatal(2, "SVX {"root proxy" if is_root_python_proxy else "AMirror"} construction {cls.canonical_id} failed: %s", {error});',
                "        end",
                *(["        end"] if deferred_python_constructor is not None else []),
                "      end else begin",
                "        // Python supplied the paired object ID during its construction path.",
                *([
                    "        if (this.__svx_remote_object_id == 0) begin",
                    f"          this.__svx_remote_object_id = {object_id};",
                    f"          svx_inheritance_registry::register_object({object_id}, this);",
                    f"        end else if (this.__svx_remote_object_id != {object_id}) begin",
                    '          $fatal(2, "SVX construction changed the reserved receiver ID");',
                    "        end",
                ] if transparent_construction and (is_root_sv_mirror and dynamic_sv_root or is_root_python_proxy) else [
                    f"        this.__svx_remote_object_id = {object_id};",
                    f"        svx_inheritance_registry::register_object({object_id}, this);",
                ]),
            ]
        )
        if is_root_python_proxy or staged_sv_root is not None or dynamic_sv_root:
            if constructor is not None and constructor.parameters:
                lines.append(f"        {record} = new();")
                for parameter in constructor.parameters:
                    value = f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})" if parameter.handle is not None else parameter.name
                    lines.append(f"        {record}.{parameter.name} = {value};")
                lines.append(f"        {record}.pack({data});")
            lines.extend([
                "        // Initialize an existing Python-origin receiver before the SV child constructor resumes.",
                f'        {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
                f"        {ok} = svx_inheritance_create_python_function({root_initialization_selector}, this.__svx_remote_object_id, {request}, {error});",
                f"        svx_payload_destroy({request});",
                f"        if (!{ok}) begin",
                "          svx_inheritance_registry::unbind(this.__svx_remote_object_id);",
                f'          $fatal(2, "SVX Python-root portion initialization {cls.canonical_id} failed: %s", {error});',
                "        end",
            ])
        lines.extend(["      end",
                      *(["      end"] if defer_sv_root else []),
                      *([f"      {context_type}::leave(this, {scope_owned});"] if transparent_construction else []),
                      "    endfunction"])
    elif reuse_base_object_id:
        if staged_python_root is not None and cls.language == "python":
            initialization_selector = (
                f'{{{json.dumps(_PYTHON_ROOT_INIT_PREFIX)}, this.__svx_python_constructor_target()}}'
                if cls.canonical_id == staged_python_root.canonical_id
                else json.dumps(_PYTHON_PORTION_INIT_PREFIX + cls.canonical_id)
            )
            lines.extend(["", f"    function new({constructor_parameters_with_optional_id});",
                          f"      bit {ok};", f"      chandle {request};", f"      string {error};",
                          f"      byte unsigned {data}[$];"])
            if constructor is not None and constructor.parameters:
                lines.append(f"      {_call_record_class_name(cls.canonical_id, 'request')} {record};")
            lines.append(f"      super.new({constructor_arguments_with_id});")
            if constructor is not None and constructor.parameters:
                lines.append(f"      {record} = new();")
                for parameter in constructor.parameters:
                    value = f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})" if parameter.handle is not None else parameter.name
                    lines.append(f"      {record}.{parameter.name} = {value};")
                lines.append(f"      {record}.pack({data});")
            lines.extend([
                f'      {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
                f"      {ok} = svx_inheritance_create_python_function({initialization_selector}, this.__svx_remote_object_id, {request}, {error});",
                f"      svx_payload_destroy({request});",
                f"      if (!{ok}) begin",
                "        svx_inheritance_registry::unbind(this.__svx_remote_object_id);",
                f'        $fatal(2, "SVX Python portion initialization {cls.canonical_id} failed: %s", {error});',
                "      end", "    endfunction"])
        else:
            lines.extend(
                [
                    "",
                    f"    function new({constructor_parameters_with_optional_id});",
                    *([f"      bit {ok};", f"      chandle {request};", f"      string {error};", f"      byte unsigned {data}[$];",
                       *([f"      {_call_record_class_name((deferred_python_constructor or cls).canonical_id, 'request')} {record};"] if constructor is not None and constructor.parameters else [])]
                      if transparent_construction and cls.language == 'sv' or deferred_python_constructor is not None else []),
                    f"      super.new({constructor_arguments if transparent_construction else constructor_arguments_with_id});",
                ]
            )
            if deferred_python_constructor is not None:
                lines.append(f"      if ({object_id} == 0) begin")
                if constructor is not None and constructor.parameters:
                    lines.append(f"        {record} = new();")
                    for parameter in constructor.parameters:
                        value = f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})" if parameter.handle else parameter.name
                        lines.append(f"        {record}.{parameter.name} = {value};")
                    lines.append(f"        {record}.pack({data});")
                lines.extend([
                    "        // Initialize Python after this proxy's SV field initializers.",
                    f'        {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
                    f"        {ok} = svx_inheritance_create_python_function({json.dumps(deferred_python_constructor.canonical_id)}, this.__svx_remote_object_id, {request}, {error});",
                    f"        svx_payload_destroy({request});",
                    f"        if (!{ok}) begin",
                    "          svx_inheritance_registry::unbind(this.__svx_remote_object_id);",
                    f'          $fatal(2, "SVX projected constructor {cls.canonical_id} failed: %s", {error});',
                    "        end", "      end",
                ])
            if transparent_construction and cls.language == 'sv':
                if constructor is not None and constructor.parameters:
                    lines.append(f"      {record} = new();")
                    for parameter in constructor.parameters:
                        value = f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})" if parameter.handle else parameter.name
                        lines.append(f"      {record}.{parameter.name} = {value};")
                    lines.append(f"      {record}.pack({data});")
                lines.extend([
                    f'      {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
                    f"      {ok} = svx_inheritance_create_python_function({json.dumps(_SV_CONSTRUCTOR_ARGUMENTS_PREFIX + cls.canonical_id)}, this.__svx_remote_object_id, {request}, {error});",
                    f"      svx_payload_destroy({request});",
                    f"      if (!{ok}) $fatal(2, \"SVX staged constructor arguments failed: %s\", {error});",
                ])
            lines.extend([*([f"      {context_type}::leave(this, {scope_owned});"] if transparent_construction else []),
                          "    endfunction"])
    elif constructor is not None and constructor.initiator == "sv":
        if super_accepts_object_id:
            raise SVXInheritanceError(
                f"SV-initiated construction of {cls.canonical_id} after a Python-to-SV "
                "projection requires an explicit generated constructor bridge"
            )
        lines.extend(
            [
                "",
                f"    function new({constructor_parameters});",
                f"      bit {ok};",
                f"      chandle {request};",
                f"      string {error};",
                f"      byte unsigned {data}[$];",
                *(
                    [
                        f"      {_call_record_class_name(cls.canonical_id, 'request')} {record};"
                    ]
                    if constructor.parameters
                    else []
                ),
                f"      super.new({constructor_arguments});",
                "      // Bind this SV-constructed instance before the Python mirror is initialized.",
                "      this.__svx_remote_object_id = svx_inheritance_registry::allocate_object_id();",
                "      svx_inheritance_registry::register_object(this.__svx_remote_object_id, this);",
            ]
        )
        if constructor.parameters:
            lines.append(f"      {record} = new();")
            for parameter in constructor.parameters:
                value = f"{_handle_adapter_name(parameter.handle)}::encode({parameter.name})" if parameter.handle is not None else parameter.name
                lines.append(f"      {record}.{parameter.name} = {value};")
            lines.append(f"      {record}.pack({data});")
        lines.extend(
            [
                f'      {request} = svx_payload_from_byte_queue({data}, "svx-inheritance", "", "application/x-svx-inheritance");',
                f"      {ok} = svx_inheritance_create_python_function({json.dumps(cls.canonical_id)}, this.__svx_remote_object_id, {request}, {error});",
                f"      svx_payload_destroy({request});",
                f"      if (!{ok}) begin",
                "        svx_inheritance_registry::unbind(this.__svx_remote_object_id);",
                f'        $fatal(2, "SVX AMirror construction {cls.canonical_id} failed: %s", {error});',
                "      end",
                "    endfunction",
            ]
        )
    else:
        super_arguments = ", ".join(
            value
            for value in (
                object_id if super_accepts_object_id else "",
                constructor_arguments,
            )
            if value
        )
        lines.extend(
            [
                "",
                f"    function new(longint unsigned {object_id}{', ' if constructor_parameters else ''}{constructor_parameters});",
                f"      super.new({super_arguments});",
                "      // Reuse the object ID already owned by the preceding cross-language bridge.",
                f"      this.__svx_remote_object_id = {object_id};",
                f"      svx_inheritance_registry::register_object({object_id}, this);",
                "    endfunction",
            ]
        )
    for method in cls.methods if is_root_python_proxy else dispatch_virtuals:
        lines.extend(_emit_sv_outbound_method(method,
                     python_base=is_root_python_proxy and not method.is_static,
                     python_static=is_root_python_proxy and method.is_static,
                     callback_boundary=callback_boundary,
                     reserve_receiver=early_receiver_binding or (
                         is_root_sv_mirror and dynamic_sv_root and transparent_construction)))
    if cls.language == 'python' and not is_root_python_proxy:
        for method in cls.methods:
            if method.is_static:
                lines.extend(_emit_sv_outbound_method(method, python_static=True))
    static_methods = tuple(method for method in cls.methods if method.is_static)
    if static_methods and not is_root_python_proxy:
        lines.extend(
            [
                "",
                "    static task svx_invoke_static(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
                "      byte unsigned bytes[$];",
                "      int offset;",
                "      response = null;",
                "      svx_payload_to_byte_queue(request, bytes);",
                "      offset = 0;",
                "      case (method_id)",
            ]
        )
        for method in static_methods:
            receiver = generated_name if cls.language == 'python' else _sv_class_reference(cls)
            lines.extend(_emit_sv_dispatch_case(method, f"{receiver}::"))
        lines.extend(
            [
                "        default: begin",
                "          ok = 0;",
                '          error = {"unsupported static member: ", method_id};',
                "        end",
                "      endcase",
                "    endtask",
            ]
        )
        lines.extend(_emit_sv_function_invoker([
            line for method in static_methods if method.timing == "function"
            for line in _emit_sv_dispatch_case(method, f"{generated_name if cls.language == 'python' else _sv_class_reference(cls)}::")
        ], static=True))
    lines.extend(
        _emit_sv_projection_invoke(
            cls,
            base_methods=tuple(method for method in base_methods if not method.is_static),
            delegate_unmatched_to_super=delegate_unmatched_to_super,
            inherited_sv_sources=inherited_sv_sources,
        )
    )
    lines.append(f"  endclass : {generated_name}")
    return lines


def _sv_field_declaration(field: Field) -> str:
    """Render a field declaration from its concrete public SvTypes codec.

    A manifest's ``sv`` type expression is suitable for parameters, while an
    unpacked collection dimension follows the member name in a declaration.
    Delegating the latter to SvTypes preserves its normal SV spelling.
    """

    if field.handle is not None:
        return f"{_sv_handle_value_type(field.handle)} {field.name}"
    try:
        import svtypes

        codec = _codec_from_spec(field.type_binding.runtime_spec())
        declaration = svtypes.sv_declaration(codec, field.name, include_initializer=True)
    except (AttributeError, ImportError, TypeError) as error:
        raise SVXInheritanceError(
            f"cannot render projected field {field.name} from its public SvTypes declaration; "
            "SvTypes must support sv_declaration(..., include_initializer=True)"
        ) from error
    if not isinstance(declaration, str) or not declaration:
        raise SVXInheritanceError(f"SvTypes emitted an invalid declaration for projected field {field.name}")
    return declaration.strip().rstrip(";")


def _emit_sv_static_gateway(
    source: ForeignClass,
    *,
    gateway_name: str,
    dispatcher_name: str,
    instance_name: str | None = None,
    source_type: str | None = None,
    inherit_source: bool = True,
) -> list[str]:
    """Emit a class-owned static dispatch gateway without allocating ``source``.

    SV gateways extend the source so qualified calls can reach protected static
    members. Python-source gateways need no inheritance. Neither is instantiated.
    A separate lightweight
    dispatcher instance is what the registry owns.
    """

    static_methods = tuple(method for method in source.methods if method.is_static)
    if not static_methods:
        return []
    source_type = source_type or _sv_class_reference(source)
    constructor_lines = []
    if inherit_source and source.constructor is not None and source.constructor.parameters:
        parameters = source.constructor.parameters
        signature = ", ".join(
            f"input {_sv_handle_value_type(parameter.handle) if parameter.handle is not None else _sv_value_type(parameter.type_binding)} {parameter.name}"
            for parameter in parameters)
        arguments = ", ".join(parameter.name for parameter in parameters)
        constructor_lines = [f"    function new({signature});",
                             f"      super.new({arguments});", "    endfunction", ""]
    lines = [
        "",
        f"  virtual class {gateway_name}" + (f" extends {source_type}" if inherit_source else "") + ";",
        *constructor_lines,
        "    static task svx_invoke_static(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
        "      byte unsigned bytes[$];",
        "      int offset;",
        "      response = null;",
        "      svx_payload_to_byte_queue(request, bytes);",
        "      offset = 0;",
        "      case (method_id)",
    ]
    for method in static_methods:
        lines.extend(_emit_sv_dispatch_case(method, f"{source_type}::"))
    lines.extend(
        [
            "        default: begin",
            "          ok = 0;",
            '          error = {"unsupported static member: ", method_id};',
            "        end",
            "      endcase",
            "    endtask",
            *_emit_sv_function_invoker([
                line for method in static_methods if method.timing == "function"
                for line in _emit_sv_dispatch_case(method, f"{source_type}::")
            ], static=True),
            f"  endclass : {gateway_name}",
            "",
            f"  class {dispatcher_name} implements svx_static_dispatchable, svx_static_function_dispatchable;",
            "    function new();",
            f"      svx_inheritance_registry::register_static({json.dumps(source.canonical_id)}, this);",
            "    endfunction",
            "",
            "    virtual task svx_invoke_static(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
            f"      {gateway_name}::svx_invoke_static(method_id, request, ok, response, error);",
            "    endtask",
            "    virtual function void svx_invoke_static_function(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
            f"      {gateway_name}::svx_invoke_static_function(method_id, request, ok, response, error);",
            "    endfunction",
            f"  endclass : {dispatcher_name}",
            "",
            f"  {dispatcher_name} {instance_name or source.generated_name + '_static_dispatcher'} = new();",
        ]
    )
    return lines


def _sv_constructor_handle_arguments(parameters: tuple[Parameter, ...]) -> tuple[list[str], list[str], str]:
    names = _sv_generated_names(
        {"object_id", "request", "ok", "error", "bytes", "offset", "constructor_request", "instance", "svx_instance"},
        (p.name for p in parameters if p.handle is not None),
    )
    declarations = []
    decode = []
    arguments = []
    for parameter in parameters:
        member = f"constructor_request.{parameter.name}"
        if parameter.handle is None:
            arguments.append(member)
            continue
        local = names[parameter.name]
        declarations.append(f"      {_sv_handle_value_type(parameter.handle)} {local};")
        decode.extend([
            f"      if (!{_handle_adapter_name(parameter.handle)}::decode({member}, {local}, error)) begin",
            "        ok = 0;", "        return;", "      end",
        ])
        arguments.append(local)
    return declarations, decode, ", ".join(arguments)


def _emit_sv_projection_factory(source: ForeignClass, helper_name: str, *, announce_receiver: bool = False) -> list[str]:
    """Factory used when Python creates the paired SV mirror/proxy object."""

    constructor = source.constructor
    if source.language == "python" and constructor is not None and constructor.initiator != "python":
        return []
    parameters = constructor.parameters if constructor is not None else ()
    handle_declarations, handle_decode, arguments = _sv_constructor_handle_arguments(parameters)
    record_name = _call_record_class_name(source.canonical_id, "request")
    factory_name = f"{helper_name}_factory"
    registration_name = f"register_{helper_name}_factory"
    lines = [
        "",
        f"  class {factory_name} implements svx_factory;",
        "    function new();",
        f"      svx_inheritance_registry::register_factory({json.dumps(source.canonical_id)}, this);",
        "    endfunction",
        "",
        "    virtual function void svx_create(longint unsigned object_id, input chandle request, output bit ok, output string error);",
    ]
    if parameters:
        lines.extend(
            [
                f"      {record_name} constructor_request;",
                f"      {helper_name} svx_instance;",
                *handle_declarations,
                "      byte unsigned bytes[$];",
            ]
        )
        lines.extend(
            [
                "      int offset;",
                "      constructor_request = new();",
                "      svx_payload_to_byte_queue(request, bytes);",
                "      offset = 0;",
                "      constructor_request.unpack(bytes, offset);",
                f'      svx_require_unpacked_all("{source.canonical_id}", "constructor request", "call request", offset, bytes.size());',
                *handle_decode,
                *([
                    f"      ok = svx_inheritance_create_python_function({json.dumps(_PYTHON_RECEIVER_EXPECT_PREFIX + source.canonical_id)}, object_id, null, error);",
                    "      if (!ok) return;",
                ] if announce_receiver else []),
                f"      svx_instance = new({arguments}, object_id);",
            ]
        )
    else:
        lines.extend([f"      {helper_name} svx_instance;",
                      *([
                          f"      ok = svx_inheritance_create_python_function({json.dumps(_PYTHON_RECEIVER_EXPECT_PREFIX + source.canonical_id)}, object_id, null, error);",
                          "      if (!ok) return;",
                      ] if announce_receiver else []),
                      "      svx_instance = new(object_id);"])
    lines.extend(
        [
            "      ok = 1;",
            '      error = "";',
            "    endfunction",
            f"  endclass : {factory_name}",
            "",
            f"  function void {registration_name}();",
            f"    static {factory_name} factory;",
            "    if (factory == null) factory = new();",
            f"    svx_inheritance_registry::register_factory({json.dumps(source.canonical_id)}, factory);",
            "  endfunction",
            "",
            f"  {factory_name} {helper_name}_factory_instance = new();",
        ]
    )
    return lines


def _projection_helper_package(source: ForeignClass, kind: str) -> str:
    """Name the generated package for one projected class portion.

    Distinct mirror helper names avoid collisions. They do not solve source
    declaration cycles: separate-package anchors are checked before emission.
    """

    if kind == "mirror":
        stem = "_".join(source.symbol.split("::")[:-1])
        # Mirror packages are SVX implementation packages.  Include the
        # class name because two classes in one SV package can require source
        # anchors at different positions.
        return "svx_mirror_sv_" + stem + "_" + source.generated_name
    elif kind == "proxy":
        # This is the public SV type namespace.  Its class keeps the source
        # Python class name; the package uses the final Python module name.
        return _sv_package_for(source)
    else:  # pragma: no cover - internal caller invariant
        raise ValueError(f"unknown projection helper kind {kind!r}")


def _emit_sv_projection_helpers(
    manifest: Manifest,
    *,
    has_call_records: bool,
    has_external_handles: bool,
) -> list[str]:
    """Materialize only mirrors/proxies implied by top-level target lineages."""

    mirrors: dict[str, tuple[ForeignClass, ForeignClass]] = {}
    proxies: dict[str, tuple[ForeignClass, ForeignClass, ForeignClass]] = {}
    lineage_contexts = _manifest_lineage_contexts(manifest)
    for plan in projection_plans(manifest):
        active_mirror: ForeignClass | None = None
        for index, current in enumerate(plan.lineage[:-1]):
            child = plan.lineage[index + 1]
            if current.language == "sv" and child.language == "python":
                active_mirror = current
                mirrors.setdefault(current.canonical_id, (current, child))
            elif current.language == "python" and child.language == "sv":
                if active_mirror is None:
                    raise SVXInheritanceError(
                        f"cannot project {current.canonical_id} into SV without a preceding SV mirror"
                    )
                proxies.setdefault(current.canonical_id, (current, active_mirror, child))

    # Python initiation is itself a request for one physical SV bridge.  It
    # must not depend on a later Python-derived target being present: the
    # generated Python mirror calls ``inheritance_create_sv`` in either case.
    for cls in manifest.classes:
        if (
            cls.language == "sv"
            and cls.constructor is not None
        ):
            mirrors.setdefault(cls.canonical_id, (cls, cls))

    packages: dict[str, list[str]] = {}
    dependencies: dict[str, set[str]] = {}
    for source, _child in mirrors.values():
        package = _projection_helper_package(source, "mirror")
        packages.setdefault(package, []).append(source.canonical_id)
    for source, _mirror, _child in proxies.values():
        package = _projection_helper_package(source, "proxy")
        packages.setdefault(package, []).append(source.canonical_id)
        mirror_package = _projection_helper_package(_mirror, "mirror")
        if mirror_package != package:
            dependencies.setdefault(package, set()).add(mirror_package)

    # A generated proxy imports its preceding mirror package.  Emit packages
    # in dependency order so a single generated source file is compilable.
    ordered_packages: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(package: str) -> None:
        if package in visited:
            return
        if package in visiting:
            raise SVXInheritanceError(f"cyclic generated projection package dependency at {package}")
        visiting.add(package)
        for dependency in sorted(dependencies.get(package, ())):
            if dependency in packages:
                visit(dependency)
        visiting.remove(package)
        visited.add(package)
        ordered_packages.append(package)

    for package in sorted(packages):
        visit(package)

    lines: list[str] = []
    for package in ordered_packages:
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        lines.extend(
            [
                "",
                "// ===========================================================================",
                "// Alternating cross-language lineage bridge package",
                f"`ifndef {guard}",
                f"`define {guard}",
                "",
                f"package {package};",
                "  import svx_pkg::*;",
                "  import svtypes_pkg::*;",
                *_sv_value_package_imports(
                    (mirrors[class_id] if class_id in mirrors else proxies[class_id])[0]
                    for class_id in packages[package]),
                *(["  import svx_call_records_pkg::*;"] if has_call_records else []),
                *(["  import svx_external_handles_pkg::*;"] if has_external_handles else []),
            ]
        )
        class_ids = sorted(set(packages[package]))
        for class_id in class_ids:
            if class_id in mirrors:
                source, _child = mirrors[class_id]
                source_package = source.symbol.split("::")[0]
                lines.append(f"  import {source_package}::*;")
            if class_id in proxies:
                _source, mirror_source, _child = proxies[class_id]
                mirror_package = _projection_helper_package(mirror_source, "mirror")
                if mirror_package != package:
                    lines.append(f"  import {mirror_package}::*;")
        for class_id in class_ids:
            if class_id in mirrors:
                source, _child = mirrors[class_id]
                ancestors = _unbridged_sv_ancestors(lineage_contexts.get(class_id, source.base_lineage))
                super_accepts_object_id = any(
                    child.canonical_id == source.canonical_id
                    for _proxy_source, _mirror_source, child in proxies.values()
                )
                lines.extend(
                    _emit_sv_projection_class(
                        source.generated_name,
                        _sv_class_reference(source),
                        source,
                        base_methods=source.methods,
                        dispatch_virtuals=_effective_virtual_methods(source, ancestors),
                        inherited_sv_sources=ancestors,
                        delegate_unmatched_to_super=super_accepts_object_id,
                        super_accepts_object_id=super_accepts_object_id,
                        reuse_base_object_id=super_accepts_object_id,
                        is_root_sv_mirror=not super_accepts_object_id,
                        deferred_python_constructor=source if not super_accepts_object_id and any(
                            mirror_source.canonical_id == source.canonical_id
                            for _proxy_source, mirror_source, _child in proxies.values()) else None,
                    )
                )
                static_methods = tuple(method for method in source.methods if method.is_static)
                if static_methods:
                    dispatcher_name = f"{source.generated_name}StaticDispatcher"
                    lines.extend(
                        [
                            "",
                            f"  class {dispatcher_name} implements svx_static_dispatchable, svx_static_function_dispatchable;",
                            "    function new();",
                            f"      svx_inheritance_registry::register_static({json.dumps(source.canonical_id)}, this);",
                            "    endfunction",
                            "",
                            "    virtual task svx_invoke_static(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
                            f"      {source.generated_name}::svx_invoke_static(method_id, request, ok, response, error);",
                            "    endtask",
                            "    virtual function void svx_invoke_static_function(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
                            f"      {source.generated_name}::svx_invoke_static_function(method_id, request, ok, response, error);",
                            "    endfunction",
                            f"  endclass : {dispatcher_name}",
                            "",
                            f"  {dispatcher_name} {source.generated_name}_static_dispatcher = new();",
                        ]
                    )
                lines.extend(_emit_sv_projection_factory(source, source.generated_name))
            if class_id in proxies:
                source, mirror_source, _child = proxies[class_id]
                lines.extend(
                    _emit_sv_projection_class(
                        source.generated_name,
                        mirror_source.generated_name,
                        source,
                        base_methods=(),
                        dispatch_virtuals=_introduced_python_virtuals(
                            source, lineage_contexts.get(source.canonical_id, source.base_lineage)),
                        delegate_unmatched_to_super=True,
                        constructor_source=mirror_source,
                        reuse_base_object_id=True,
                        deferred_python_constructor=mirror_source,
                    )
                )
                if any(method.is_static for method in source.methods):
                    names = _sv_generated_names(
                        {item.generated_name for item in _all_manifest_classes(manifest)},
                        (source.generated_name + 'StaticGateway', source.generated_name + 'StaticDispatcher',
                         source.generated_name + '_static_dispatcher'),
                    )
                    lines.extend(_emit_sv_static_gateway(
                        source, source_type=source.generated_name, inherit_source=False,
                        gateway_name=names[source.generated_name + 'StaticGateway'],
                        dispatcher_name=names[source.generated_name + 'StaticDispatcher'],
                        instance_name=names[source.generated_name + '_static_dispatcher'],
                    ))
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])
    return lines


def _emit_sv_implementation_factory(cls: ForeignClass) -> list[str]:
    """Expose typed implementation selection without application ABI glue."""

    if cls.constructor is None or cls.constructor.initiator != "python":
        return []
    name = cls.generated_name + "Factory"
    parameters = cls.constructor.parameters
    handle_declarations, handle_decode, arguments = _sv_constructor_handle_arguments(parameters)
    return [
        "",
        "  // Public typed factory: specialize with the application's SV-derived class.",
        f"  class {name} #(type Implementation = {cls.generated_name}) implements svx_factory;",
        "    function new();",
        f"      svx_inheritance_registry::register_factory({json.dumps(cls.canonical_id)}, this);",
        "    endfunction",
        "",
        "    virtual function void svx_create(longint unsigned object_id, input chandle request, output bit ok, output string error);",
        *(
            [f"      {cls.generated_name}::constructor_request_t constructor_request;"]
            if parameters else []
        ),
        "      Implementation svx_instance;",
        *handle_declarations,
        *(
            [f"      constructor_request = {cls.generated_name}::svx_decode_constructor_request(request);"]
            if parameters else []
        ),
        *handle_decode,
        f"      svx_instance = new(object_id{', ' if arguments else ''}{arguments});",
        "      ok = 1;",
        '      error = "";',
        "    endfunction",
        f"  endclass : {name}",
    ]


def emit_sv_mirrors(manifest: Manifest) -> str:
    """Emit target-scoped SV AMirror and Proxy projection helpers."""

    _require_executable_projection_plans(manifest)
    projected = _projected_class_ids(manifest)
    packages: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "python" and cls.canonical_id not in projected:
            packages.setdefault(
                _sv_package_for(cls),
                [],
            ).append(cls)

    lines = _generated_sv_header(manifest)
    record_types = _manifest_sv_record_types(manifest)
    if record_types:
        imported_packages = sorted(
            {
                binding.sv.split("::", 1)[0]
                for cls in _all_manifest_classes(manifest)
                for binding in [
                    *(
                        parameter.type_binding
                        for parameter in (
                            cls.constructor.parameters if cls.constructor else ()
                        )
                    ),
                    *(
                        parameter.type_binding
                        for method in cls.methods
                        for parameter in method.parameters
                    ),
                    *(method.return_type for method in cls.methods if method.return_type),
                ]
                if "::" in binding.sv and binding.sv.split("::", 1)[0] != "svtypes_pkg"
            }
        )
        lines.extend(
            [
                "",
                "// ===========================================================================",
                "// Private SvTypes call records",
                "package svx_call_records_pkg;",
                "  import svtypes_pkg::*;",
                *(f"  import {package}::*;" for package in imported_packages),
            ]
        )
        lines.extend("  " + declaration for declaration in _manifest_sv_collection_typedefs(manifest))
        for record_type in record_types:
            lines.extend(["", record_type.to_sv_obj(1)])
        lines.extend(["endpackage : svx_call_records_pkg", ""])
    external_handle_bindings = _manifest_handle_bindings(manifest)
    lines.extend(_emit_sv_external_handle_adapters(manifest))
    record_import = ["  import svx_call_records_pkg::*;"] if record_types else []
    external_handle_import = ["  import svx_external_handles_pkg::*;"] if external_handle_bindings else []
    for package, classes in sorted(packages.items()):
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        lines.extend([
            "",
            "// ===========================================================================",
            "// Public Python-to-SystemVerilog proxy projections",
            f"`ifndef {guard}",
            f"`define {guard}",
            "",
            f"package {package};",
            "  import svx_pkg::*;",
            "  import svtypes_pkg::*;",
            *_sv_value_package_imports(classes),
            *record_import,
            *external_handle_import,
        ])
        generated_names = {cls.generated_name for cls in classes}
        for cls in classes:
            if (
                cls.constructor is not None
                and cls.constructor.initiator == "python"
                and cls.generated_name + "Factory" in generated_names
            ):
                raise SVXInheritanceError(
                    f"generated implementation factory name collision in {package}: "
                    f"{cls.generated_name}Factory"
                )
        for cls in sorted(classes, key=lambda item: item.name):
            proxy_name = cls.generated_name
            lines.extend(["", f"  // Generated SV projection for {cls.canonical_id}", f"  virtual class {proxy_name} implements svx_dispatchable, svx_function_dispatchable;", "    longint unsigned __svx_remote_object_id;"])
            for field in cls.fields:
                lines.append(f"    {_sv_field_declaration(field)};")
            lines.extend(["", "    function new(longint unsigned object_id);", "      __svx_remote_object_id = object_id;", "      svx_inheritance_registry::register_object(object_id, this);", "    endfunction"])
            if cls.constructor is not None and cls.constructor.parameters:
                record_name = _call_record_class_name(cls.canonical_id, "request")
                lines.extend(
                    [
                        "",
                        f"    typedef {record_name} constructor_request_t;",
                        "",
                        "    static function constructor_request_t svx_decode_constructor_request(input chandle request);",
                        "      constructor_request_t value;",
                        "      byte unsigned bytes[$];",
                        "      int offset;",
                        "      value = new();",
                        "      svx_payload_to_byte_queue(request, bytes);",
                        "      offset = 0;",
                        "      value.unpack(bytes, offset);",
                        f'      svx_require_unpacked_all("{cls.canonical_id}", "constructor request", "call request", offset, bytes.size());',
                        "      return value;",
                        "    endfunction",
                    ]
                )
            for method in cls.methods:
                lines.extend(_emit_sv_outbound_method(method, python_static=method.is_static))
            lines.extend(["", "    virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);", "      byte unsigned bytes[$];", "      int offset;", "      response = null;", "      svx_payload_to_byte_queue(request, bytes);", "      offset = 0;", "      case (method_id)"])
            for method in cls.methods:
                lines.extend(_emit_sv_dispatch_case(method))
            for field in cls.fields:
                lines.extend(_emit_sv_field_dispatch_cases(cls, field))
            lines.extend(["        default: begin", "          ok = 0;", "          error = {\"unsupported method: \", method_id};", "        end", "      endcase", "    endtask"])
            function_cases = [
                line for method in cls.methods if method.timing == "function"
                for line in _emit_sv_dispatch_case(method)
            ]
            for field in cls.fields:
                function_cases.extend(_emit_sv_field_dispatch_cases(cls, field))
            lines.extend(_emit_sv_function_invoker(function_cases))
            lines.append(f"  endclass : {proxy_name}")
            lines.extend(_emit_sv_implementation_factory(cls))
            if any(method.is_static for method in cls.methods):
                names = _sv_generated_names(generated_names, (
                    proxy_name + "StaticGateway", proxy_name + "StaticDispatcher",
                    proxy_name + "_static_dispatcher",
                ))
                generated_names.update(names.values())
                lines.extend(_emit_sv_static_gateway(
                    cls, source_type=proxy_name, inherit_source=False,
                    gateway_name=names[proxy_name + "StaticGateway"],
                    dispatcher_name=names[proxy_name + "StaticDispatcher"],
                    instance_name=names[proxy_name + "_static_dispatcher"],
                ))
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])

    # A standalone Python mirror may expose static SV members without having a
    # downstream Python-derived target, hence no AMirror package. Give those
    # classes their own no-instance gateway rather than silently omitting the
    # static method from the generated Python API.
    mirrored_sources: set[str] = set()
    for plan in projection_plans(manifest):
        for index, current in enumerate(plan.lineage[:-1]):
            if plan.lineage[index + 1].language == "python" and current.language == "sv":
                mirrored_sources.add(current.canonical_id)
    static_packages: dict[str, list[ForeignClass]] = {}
    for source in _all_manifest_classes(manifest):
        if (
            source.language != "sv"
            or source.canonical_id in mirrored_sources
            or not any(method.is_static for method in source.methods)
        ):
            continue
        package = "svx_static_" + "_".join(source.symbol.split("::")[:-1]) + "_" + source.generated_name + "_pkg"
        static_packages.setdefault(package, []).append(source)
    for package, sources in sorted(static_packages.items()):
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        source_package = sources[0].symbol.split("::")[0]
        lines.extend(
            [
                "",
                "// ===========================================================================",
                "// Static SystemVerilog gateway projections",
                f"`ifndef {guard}",
                f"`define {guard}",
                "",
                f"package {package};",
                "  import svx_pkg::*;",
                "  import svtypes_pkg::*;",
                *_sv_value_package_imports(sources),
                *record_import,
                *external_handle_import,
                f"  import {source_package}::*;",
            ]
        )
        occupied = {source.generated_name for source in sources}
        for source in sorted(sources, key=lambda item: item.canonical_id):
            gateway = source.generated_name + "StaticGateway"
            dispatcher = source.generated_name + "StaticDispatcher"
            instance = source.generated_name + "_static_dispatcher"
            names = _sv_generated_names(occupied, (gateway, dispatcher, instance))
            occupied.update(names.values())
            lines.extend(_emit_sv_static_gateway(
                source, gateway_name=names[gateway], dispatcher_name=names[dispatcher],
                instance_name=names[instance]))
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])

    lines.extend(
        [
            "",
            "// ===========================================================================",
            "// Alternating cross-language lineage bridge helpers",
        ]
    )
    lines.extend(
        _emit_sv_projection_helpers(
            manifest,
            has_call_records=bool(record_types),
            has_external_handles=bool(external_handle_bindings),
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _projection_stage_filename(position: str, canonical_id: str) -> str:
    """Return a deterministic include filename for one source-order anchor."""

    stem = re.sub(r"[^A-Za-z0-9]+", "_", canonical_id).strip("_")
    digest = hashlib.sha256(canonical_id.encode("utf-8")).hexdigest()[:10]
    return f"{position}_{stem}_{digest}.svh"


def emit_sv_mirror_stages(manifest: Manifest) -> dict[str, str]:
    """Split generated projection helpers at their required SV source anchors.

    A single generated source is sufficient for a one-boundary projection. An
    alternating lineage is different: ``BProxy`` must be visible before a user
    declaration ``class C extends BProxy``, while ``CMirror extends C`` cannot
    be parsed until after that declaration.  SystemVerilog does not permit a
    forward base class in this situation.  This function leaves ordinary
    generated declarations in ``common.svh`` and emits each helper package at
    the exact ``before`` or ``after`` class anchor required by its lineage.

    The returned paths are relative names suitable for one generated directory.
    A caller includes ``common.svh`` once, then includes each anchor file at the
    corresponding global source position.  Conflicting anchors for a generated
    package are rejected rather than producing order-dependent SV source.
    """

    _require_executable_projection_plans(manifest)
    package_anchors: dict[str, tuple[str, str]] = {}

    def record_anchor(package: str, anchor: tuple[str, str]) -> None:
        existing = package_anchors.setdefault(package, anchor)
        if existing != anchor:
            raise SVXInheritanceError(
                "one generated SystemVerilog projection package requires "
                f"incompatible source anchors {existing!r} and {anchor!r}"
            )

    for plan in projection_plans(manifest):
        for index, current in enumerate(plan.lineage[:-1]):
            child = plan.lineage[index + 1]
            if current.language == "sv" and child.language == "python":
                package = _projection_helper_package(current, "mirror")
                record_anchor(package, ("after", current.canonical_id))
            elif current.language == "python" and child.language == "sv":
                package = _projection_helper_package(current, "proxy")
                record_anchor(package, ("before", child.canonical_id))

    combined = emit_sv_mirrors(manifest)
    common = combined
    staged: dict[str, list[str]] = {}
    for package, (position, canonical_id) in sorted(package_anchors.items()):
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        begin = f"`ifndef {guard}\n"
        end = f"`endif // {guard}"
        start = common.find(begin)
        if start < 0:
            raise SVXInheritanceError(
                f"generated projection package {package!r} is missing from SV output"
            )
        finish = common.find(end, start)
        if finish < 0:
            raise SVXInheritanceError(
                f"generated projection package {package!r} has no closing include guard"
            )
        finish += len(end)
        block = "\n".join(
            [
                "// Generated by svx inheritance-gen. Do not edit.",
                f"// Manifest: {manifest.schema_uri} v{manifest.schema_version}; generator ABI {manifest.generator_abi_version}.",
                f"// Role: lineage bridge inserted {position} {canonical_id}.",
                "",
                common[start:finish].strip(),
                "",
            ]
        )
        common = common[:start] + common[finish:]
        filename = _projection_stage_filename(position, canonical_id)
        staged.setdefault(filename, []).append(block)

    result = {"common.svh": common.rstrip() + "\n"}
    for filename, blocks in sorted(staged.items()):
        result[filename] = "\n".join(blocks)
    return result


def artifact_manifest(
    manifest: Manifest,
    python_sources: dict[PurePosixPath, str],
    sv_source: str | None = None,
    *,
    python_path_prefix: str = "",
    sv_path: str = "mirrors.sv",
    sv_sources: dict[PurePosixPath, str] | None = None,
) -> dict[str, Any]:
    """Describe generated inheritance artifacts for startup compatibility checks."""

    from .runtime import SVX_RUNTIME_ABI_VERSION

    artifacts = [
        {
            "language": "python",
            "path": (PurePosixPath(python_path_prefix) / path).as_posix(),
            "module": ".".join(
                path.parent.parts
                if path.name == "__init__.py"
                else path.with_suffix("").parts
            ),
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        }
        for path, source in sorted(python_sources.items(), key=lambda item: item[0].as_posix())
    ]
    if sv_sources is None:
        if sv_source is None:
            raise TypeError("artifact_manifest requires sv_source or sv_sources")
        sv_sources = {PurePosixPath(sv_path): sv_source}
    artifacts.extend(
        {
            "language": "systemverilog",
            "path": path.as_posix(),
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        }
        for path, source in sorted(sv_sources.items(), key=lambda item: item[0].as_posix())
    )

    def record_metadata(
        owner_id: str,
        kind: str,
        fields: tuple[tuple[str, TypeBinding], ...],
    ) -> dict[str, Any] | None:
        if not fields:
            return None
        import svtypes

        record_type = _sv_record_type(owner_id, kind, fields)
        return {
            "unified_type_name": _call_record_type_id(owner_id, kind),
            "sv_class": _call_record_class_name(owner_id, kind),
            "encoding_descriptor": svtypes.encoding_descriptor(record_type).to_dict(),
        }

    bindings: dict[str, TypeBinding] = {}
    callables: list[dict[str, Any]] = []
    constructors: list[dict[str, Any]] = []
    declarations = _all_manifest_classes(manifest)
    for cls in declarations:
        for field in cls.fields:
            bindings[field.type_binding.unified_type_name] = field.type_binding
        if cls.constructor is not None:
            for parameter in cls.constructor.parameters:
                bindings[parameter.type_binding.unified_type_name] = parameter.type_binding
            constructors.append(
                {
                    "canonical_class_id": cls.canonical_id,
                    "initiator": cls.constructor.initiator,
                    "request_record": record_metadata(
                        cls.canonical_id,
                        "request",
                        tuple(
                            (parameter.name, parameter.type_binding)
                            for parameter in cls.constructor.parameters
                        ),
                    ),
                    "request_fields": [
                        {
                            "name": parameter.name,
                            "unified_type_name": parameter.type_binding.unified_type_name,
                        }
                        for parameter in cls.constructor.parameters
                    ],
                }
            )
        for method in cls.methods:
            for parameter in method.parameters:
                bindings[parameter.type_binding.unified_type_name] = parameter.type_binding
            if method.return_type is not None:
                bindings[method.return_type.unified_type_name] = method.return_type
            callables.append(
                {
                    "canonical_id": method.canonical_id,
                    "request_record": record_metadata(
                        method.canonical_id,
                        "request",
                        tuple(
                            (parameter.name, parameter.type_binding)
                            for parameter in _request_parameters(method)
                        ),
                    ),
                    "response_record": record_metadata(
                        method.canonical_id,
                        "response",
                        tuple(
                            (parameter.name, parameter.type_binding)
                            for parameter in _response_parameters(method)
                        )
                        + (
                            ((_method_return_slot(method), method.return_type),)
                            if method.return_type is not None
                            else ()
                        ),
                    ),
                    "request_fields": [
                        {
                            "name": parameter.name,
                            "direction": parameter.direction,
                            "unified_type_name": parameter.type_binding.unified_type_name,
                        }
                        for parameter in _request_parameters(method)
                    ],
                    "response_fields": [
                        {
                            "name": parameter.name,
                            "direction": parameter.direction,
                            "unified_type_name": parameter.type_binding.unified_type_name,
                        }
                        for parameter in _response_parameters(method)
                    ]
                    + (
                        [
                            {
                                "name": _method_return_slot(method),
                                "direction": "return",
                                "unified_type_name": method.return_type.unified_type_name,
                            }
                        ]
                        if method.return_type is not None
                        else []
                    ),
                }
            )
    projected = _projected_class_ids(manifest)
    python_mirror_ids = {
        step.source_class_id
        for plan in projection_plans(manifest)
        for step in plan.steps
        if step.kind == "sv_mirror"
    }
    python_mirror_ids.update(
        cls.canonical_id
        for cls in manifest.classes
        if cls.language == "sv" and cls.canonical_id not in projected
    )
    python_mirror_ids.update(source.canonical_id for source in _python_root_artifact_portions(manifest)
                             if source.language == "sv")
    # Complete-target views may be materialized independently of a boundary
    # step. Include their declared identities only when a class was emitted.
    for source in python_sources.values():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ClassDef):
                for declaration in node.body:
                    if (isinstance(declaration, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == "__svx_foreign_class_id__"
                                    for target in declaration.targets)
                            and isinstance(declaration.value, ast.Constant)
                            and isinstance(declaration.value.value, str)
                            and declaration.value.value.startswith("sv://")):
                        python_mirror_ids.add(declaration.value.value)
    sv_proxy_ids = {
        step.source_class_id
        for plan in projection_plans(manifest)
        for step in plan.steps
        if step.kind == "sv_proxy"
    }
    sv_proxy_ids.update(
        cls.canonical_id
        for cls in manifest.classes
        if cls.language == "python" and cls.canonical_id not in projected
    )
    python_adapter_ids = {
        cls.canonical_id
        for cls in manifest.classes
        if cls.language == "python" and cls.canonical_id not in projected
    }
    python_adapter_ids.update(source.canonical_id for source in _python_root_artifact_portions(manifest)
                              if source.language == "python")

    return {
        "schema_uri": "https://svx.dev/schema/generated-artifacts/v1",
        "schema_version": "1.0.0",
        "generator_abi_version": GENERATOR_ABI_VERSION,
        "svx_runtime_abi_version": SVX_RUNTIME_ABI_VERSION,
        "inheritance_manifest": {
            "schema_uri": manifest.schema_uri,
            "schema_version": manifest.schema_version,
        },
        "required_runtime_capabilities": list(
            manifest.required_runtime_capabilities
        ),
        "svtypes": {
            "required_package_major": 1,
        },
        "classes": sorted(cls.canonical_id for cls in manifest.classes),
        "generated_types": [
            {
                "canonical_class_id": cls.canonical_id,
                **(
                    {"python_fqn": _public_python_type_for(cls)}
                    if cls.canonical_id in python_mirror_ids
                    else {}
                ),
                **(
                    {"systemverilog_fqn": _public_sv_type_for(cls)}
                    if cls.canonical_id in sv_proxy_ids
                    else {}
                ),
                **(
                    {"python_adapter_fqn": _python_adapter_type_for(cls)}
                    if cls.canonical_id in python_adapter_ids
                    else {}
                ),
            }
            for cls in declarations
            if (
                cls.canonical_id in python_mirror_ids
                or cls.canonical_id in sv_proxy_ids
                or cls.canonical_id in python_adapter_ids
            )
        ],
        "constructors": sorted(
            constructors, key=lambda item: item["canonical_class_id"]
        ),
        "callables": sorted(callables, key=lambda item: item["canonical_id"]),
        "types": [
            binding.runtime_spec()
            for _, binding in sorted(bindings.items())
        ],
        "artifacts": artifacts,
    }


def obsolete_generated_sources(output_dir: Path, sources: dict, inventory: str) -> list[Path]:
    index = output_dir / inventory
    if not index.exists():
        return []
    try:
        previous = json.loads(index.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise SVXInheritanceError(f"invalid generated-file inventory {index}") from error
    if not isinstance(previous, list) or not all(isinstance(item, str) for item in previous):
        raise SVXInheritanceError(f"invalid generated-file inventory {index}")
    expected = {(output_dir / path).resolve() for path in sources}
    obsolete = []
    seen: set[Path] = set()
    for relative in previous:
        entry = PurePosixPath(relative)
        if entry.is_absolute() or ".." in entry.parts:
            raise SVXInheritanceError(f"generated-file inventory requires relative paths without escapes: {relative}")
        if not relative or str(entry) != relative or relative == ".":
            raise SVXInheritanceError(f"non-canonical generated-file inventory path: {relative}")
        path = output_dir / relative
        resolved = path.resolve()
        try:
            resolved.relative_to(output_dir.resolve())
        except ValueError as error:
            raise SVXInheritanceError(f"generated-file inventory escapes output directory: {relative}") from error
        if resolved in seen:
            raise SVXInheritanceError(f"duplicate generated-file inventory path: {relative}")
        seen.add(resolved)
        if resolved not in expected and path.is_symlink():
            raise SVXInheritanceError(f"refusing to retire symlink from generated-file inventory: {path}")
        if resolved not in expected and path.is_file():
            obsolete.append(path)
    return obsolete


def validate_generated_sources(sources: dict, output_dir: Path, inventory: str | None = None) -> list[Path]:
    """Preflight ownership and paths before changing a generated output set."""

    root = output_dir.resolve()
    targets = [output_dir / relative for relative in sources]
    if inventory is not None:
        targets.append(output_dir / inventory)
    for path in targets:
        if not path.resolve().is_relative_to(root):
            raise SVXInheritanceError(f"generated target escapes output directory: {path}")
        validate_output_path(path)
    for relative in sources:
        path = output_dir / relative
        if path.is_file() and not path.read_bytes().startswith((
            b"# Generated by svx inheritance-gen.", b"// Generated by svx inheritance-gen."
        )):
            raise SVXInheritanceError(f"refusing to overwrite non-generated file {path}")
    if inventory is None:
        return []
    obsolete = obsolete_generated_sources(output_dir, sources, inventory)
    for path in obsolete:
        if not path.read_text(encoding="utf-8").startswith((
            "# Generated by svx inheritance-gen.", "// Generated by svx inheritance-gen."
        )):
            raise SVXInheritanceError(f"refusing to delete non-generated file {path}")
    return obsolete


def validate_output_path(path: Path) -> None:
    """Reject known filesystem conflicts before any generated output is written."""
    if path.exists() and not path.is_file():
        raise SVXInheritanceError(f"generated target is not a file: {path}")
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise SVXInheritanceError(f"generated target parent is not a directory: {parent}")


def write_generated_sources(sources: dict, output_dir: Path, inventory: str) -> list[Path]:
    obsolete = validate_generated_sources(sources, output_dir, inventory)
    written: list[Path] = []
    for relative_path, text in sources.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, text)
        written.append(path)
    for path in obsolete:
        path.unlink()
    write_text_atomic(output_dir / inventory, generated_inventory_text(sources))
    return written


def generated_inventory_text(sources: dict) -> str:
    return json.dumps(sorted(str(path) for path in sources), indent=2) + "\n"


def recover_obsolete_artifacts(previous: dict, artifact_path: Path, output_dir: Path,
                               sources: dict, language: str,
                               protected: Iterable[Path] = ()) -> list[Path]:
    """Recover historical ownership only from unchanged recorded artifacts."""
    entries = previous.get("artifacts")
    if not isinstance(entries, list):
        raise SVXInheritanceError(f"cannot recover generated inventory from {artifact_path}: missing artifacts list")
    root = output_dir.resolve()
    current = {(output_dir / path).resolve() for path in sources}
    current.update(path.resolve() for path in protected)
    recovered = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SVXInheritanceError(f"invalid artifact entry in {artifact_path}")
        if entry.get("language") != language:
            continue
        relative, digest = entry.get("path"), entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SVXInheritanceError(f"invalid recorded artifact path/hash in {artifact_path}")
        path = artifact_path.parent / relative
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or resolved in current:
            continue
        if path.is_symlink():
            raise SVXInheritanceError(f"refusing to retire symlink from recovered inventory: {path}")
        if not path.exists():
            continue
        if not path.is_file():
            raise SVXInheritanceError(f"recovered generated target is not a file: {path}")
        contents = path.read_bytes()
        if not contents.startswith((b"# Generated by svx inheritance-gen.", b"// Generated by svx inheritance-gen.")) or hashlib.sha256(contents).hexdigest() != digest:
            raise SVXInheritanceError(f"refusing to retire modified artifact from recovered inventory: {path}")
        recovered.add(path)
    return sorted(recovered)


def write_python_mirrors(manifest: Manifest, output_dir: Path) -> list[Path]:
    return write_generated_sources(
        emit_python_mirrors(manifest), output_dir, ".svx-generated-python.json"
    )


def _stage_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        return Path(temporary)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_text_atomic(path: Path, text: str) -> None:
    """Replace changed artifacts atomically; preserve unchanged build inputs."""

    if path.is_file() and path.read_bytes() == text.encode("utf-8"):
        return
    temporary = _stage_text(path, text)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_atomic_group(outputs: Mapping[Path, str]) -> None:
    """Restore a metadata group on handled publication failure, preserving files.

    Readers may observe an incomplete group during replacement and must validate
    its contract. This is not crash-atomic publication or multi-writer locking.
    """
    paths = list(outputs)
    resolved = {path.resolve() for path in paths}
    if len(resolved) != len(paths):
        raise SVXInheritanceError('duplicate grouped output paths')
    if any(parent in resolved for path in resolved for parent in path.parents):
        raise SVXInheritanceError('grouped output paths conflict')
    changed = {}
    original = {}
    for path, text in outputs.items():
        if path.is_symlink():
            raise SVXInheritanceError(f'refusing grouped symlink output: {path}')
        validate_output_path(path)
        current = path.read_bytes() if path.is_file() else None
        if current != text.encode('utf-8'):
            changed[path] = text
            original[path] = current
    staged = {}
    saved = {}
    attempted = []
    recovery_failed = False
    complete = False
    created_directories = set()
    try:
        # Prepare every new file before moving any existing output.
        for path, text in changed.items():
            parent = path.parent
            while not parent.exists():
                created_directories.add(parent)
                parent = parent.parent
            staged[path] = _stage_text(path, text)
        for path in changed:
            current = path.read_bytes() if path.is_file() else None
            if current != original[path] or path.exists() and not path.is_file():
                raise SVXInheritanceError(f'output changed independently before publication: {path}')
            backup = None
            if original[path] is not None:
                descriptor, name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.bak', dir=path.parent)
                os.close(descriptor)
                backup = Path(name)
                backup.unlink()
            saved[path] = backup
            attempted.append(path)
            if backup is not None:
                path.replace(backup)
            staged[path].replace(path)
        complete = True
    except BaseException as error:
        failures = []
        for path in reversed(attempted):
            backup = saved[path]
            try:
                if backup is not None and not backup.exists():
                    if path.is_file() and path.read_bytes() == original[path]:
                        continue
                    raise OSError('original backup is unavailable')
                if path.exists() and path.read_bytes() != changed[path].encode('utf-8'):
                    raise OSError('output changed independently during publication')
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    backup.replace(path)
            except OSError as restore_error:
                failures.append(f'{path}: {restore_error}; saved original: {backup}')
        if failures:
            recovery_failed = True
            raise SVXInheritanceError(
                'group publication failed and recovery is incomplete; preserved saved originals: '
                + '; '.join(failures)) from error
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        if not recovery_failed:
            for backup in saved.values():
                if backup is not None:
                    backup.unlink(missing_ok=True)
        if not complete:
            for directory in sorted(created_directories, key=lambda path: len(path.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass


def bind_instance(object_id: int, instance: object) -> None:
    """Bind a Python object for an explicitly generated SV inheritance proxy."""

    if object_id <= 0 or object_id >= (1 << 64):
        raise ValueError("SVX inheritance object id must be an unsigned non-zero 64-bit value")
    from . import _native

    _native.inheritance_bind(object_id, instance)


def unbind_instance(object_id: int) -> None:
    """Release a binding previously created with :func:`bind_instance`."""

    from . import _native

    _reserved_python_receivers.pop(object_id, None)
    _native.inheritance_unbind(object_id)


def close_instance(object_id: object) -> None:
    """Release a cross-language instance, or a previously obtained object ID.

    Passing the instance avoids depending on generated private ID attributes.
    The integer form and its keyword remain supported for existing consumers.
    Repeated close follows the native idempotent release path.
    """

    from . import _native

    instance = None
    if isinstance(object_id, bool):
        raise TypeError("SVX inheritance object ID must not be a boolean")
    if not isinstance(object_id, int):
        instance = object_id
        class_id = getattr(instance, "__svx_foreign_class_id__", None)
        if not isinstance(class_id, str) or not class_id:
            raise TypeError("close_instance() requires an SVX cross-language instance or object ID")
        object_id = getattr(instance, "_svx_remote_object_id", None)
        if not isinstance(object_id, int) or isinstance(object_id, bool):
            raise SVXInheritanceError("close_instance() requires an instance with an allocated object ID")
    if object_id <= 0 or object_id >= (1 << 64):
        raise ValueError("SVX inheritance object ID must be an unsigned non-zero 64-bit value")
    if instance is not None:
        bound = _native.inheritance_get(object_id)
        if bound is not None and bound is not instance:
            raise SVXInheritanceError("close_instance() object ID is bound to a different instance")
    _native.inheritance_close(object_id)


@inheritance_boundary('Python -> SV')
def call_sv(object_id: int, method_id: str, request: bytes = b"") -> bytes:
    """Call a manifest-generated SV adapter from an active SVX context."""

    if not isinstance(method_id, str) or not method_id:
        raise ValueError("SVX inheritance method_id must be a non-empty string")
    if not isinstance(request, bytes):
        raise TypeError("SVX inheritance request must be bytes")
    from . import _native

    contract = _method_contracts.get(method_id)
    if contract is None or contract.timing != "function":
        from .callback_context import require_blocking_operations_allowed
        require_blocking_operations_allowed(f"SV task {method_id}")
    try:
        if contract is not None and contract.timing == "function":
            return _native.inheritance_call_sv(object_id, method_id, request, function=True)
        return _native.inheritance_call_sv(object_id, method_id, request)
    except SVXCancellationError:
        raise
    except RuntimeError as error:
        message = str(error)
        code = "remote_error"
        if message.startswith("SVX1|"):
            parts = message.split("|", 4)
            if len(parts) == 5:
                _, code, remote_object_id, remote_method_id, message = parts
                try:
                    object_id = int(remote_object_id)
                except ValueError:
                    pass
                method_id = remote_method_id
        raise SVXRemoteError(object_id, method_id, message, code=code) from error


@inheritance_boundary('Python -> SV static', receiver=None)
def call_sv_static(class_id: str, method_id: str, request: bytes = b"") -> bytes:
    """Call a generated static SV adapter without creating an object instance."""

    if not isinstance(class_id, str) or not class_id:
        raise ValueError("SVX inheritance class_id must be a non-empty string")
    if not isinstance(method_id, str) or not method_id:
        raise ValueError("SVX inheritance method_id must be a non-empty string")
    if not isinstance(request, bytes):
        raise TypeError("SVX inheritance request must be bytes")
    from . import _native

    contract = _method_contracts.get(method_id)
    if contract is None or contract.timing != "function":
        from .callback_context import require_blocking_operations_allowed
        require_blocking_operations_allowed(f"SV static task {method_id}")
    try:
        if contract is not None and contract.timing == "function":
            return _native.inheritance_call_sv_static(class_id, method_id, request, function=True)
        return _native.inheritance_call_sv_static(class_id, method_id, request)
    except SVXCancellationError:
        raise
    except RuntimeError as error:
        message = str(error)
        code = "remote_error"
        if message.startswith("SVX1|"):
            parts = message.split("|", 4)
            if len(parts) == 5:
                _, code, _remote_object_id, remote_method_id, message = parts
                method_id = remote_method_id
        raise SVXRemoteError(0, method_id, message, code=code) from error


@dataclass
class _CallContract:
    parameters: tuple[tuple[str, str, dict[str, Any]], ...]
    request_fields: tuple[tuple[str, dict[str, Any]], ...]
    response_fields: tuple[tuple[str, dict[str, Any]], ...]
    timing: str = "task"
    request_schema: Any | None = dataclass_field(default=None, compare=False, repr=False)
    response_schema: Any | None = dataclass_field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class _RecordSchemaAdapter:
    schema: Any
    value_type: type

    def pack(self, value: Any, context: Any = None) -> bytes:
        return value.pack(value, context)

    def unpack(self, payload: bytes, context: Any = None):
        prototype = self.value_type.codec_template(
            session=context.session if context is not None else None
        )
        return prototype.unpack(payload, context)


_method_contracts: dict[str, _CallContract] = {}
_constructor_contracts: dict[str, _CallContract] = {}
_python_subclasses: dict[str, type] = {}
_python_static_methods: dict[str, tuple[type, Any]] = {}
_python_static_sources: dict[str, tuple[str, tuple[str, ...]]] = {}
_external_handle_targets: set[str] = set()
_vif_views: dict[str, type] = {}

_natural_constructor_segments = ConstructorContinuations()
_natural_constructor_boundary: ContextVar[tuple[Any, int, str] | None] = ContextVar(
    "svx_natural_constructor_boundary", default=None)


def _rollback_natural_constructor(instance: Any, object_id: int, error: BaseException) -> None:
    from .declarations import SVMirror

    for action, cleanup in (
        ("unwind constructor portions", lambda: _natural_constructor_segments.abort(object_id, error)),
        ("close paired receiver", lambda: close_instance(object_id)),
    ):
        try:
            cleanup()
        except BaseException as cleanup_error:
            error.add_note(f"construction could not {action}: {cleanup_error}")
    SVMirror._svx_retire_failed_python_companion(instance, error)


def _prepare_natural_constructor(instance: Any, object_id: int, python_class_id: str,
                                 sv_class_id: str, payload: bytes) -> bytes:
    """Run one original Python portion to its generated SV Mirror boundary."""
    source = _python_subclasses.get(python_class_id)
    if source is None or not isinstance(instance, source):
        raise SVXInheritanceError(f"no natural constructor receiver for {python_class_id}")
    if (not isinstance(object_id, int) or isinstance(object_id, bool)
            or not 0 < object_id < (1 << 64)):
        raise SVXInheritanceError("natural constructor requires a reserved receiver ID")

    def initialize():
        token = _natural_constructor_boundary.set((instance, object_id, sv_class_id))
        try:
            source.__init__(instance, *arguments)
        finally:
            _natural_constructor_boundary.reset(token)

    try:
        arguments = _decode_constructor_arguments(python_class_id, payload)
        return _natural_constructor_segments.prepare(object_id, sv_class_id, initialize, owner=instance)
    except BaseException as error:
        _rollback_natural_constructor(instance, object_id, error)
        raise


def _suspend_natural_constructor(instance: Any, class_id: str, values: dict[str, Any]) -> bool:
    boundary = _natural_constructor_boundary.get()
    if boundary is None or boundary[0] is not instance:
        return False
    _, object_id, expected = boundary
    if class_id != expected:
        raise SVXInheritanceError(f"natural constructor reached {class_id}, expected {expected}")
    _natural_constructor_segments.suspend(object_id, class_id, encode_constructor(class_id, values))
    return True


def _resume_natural_constructor(instance: Any, object_id: int, sv_class_id: str) -> None:
    """Resume only after native identity and projected storage have been bound."""
    if getattr(instance, "_svx_remote_object_id", None) != object_id:
        raise SVXInheritanceError("natural constructor receiver is not bound to its reserved ID")
    try:
        fields = getattr(type(instance), "__svx_root_field_ids__", None)
        if fields:
            instance._svx_bind_projected_fields(fields)
        else:
            instance._svx_bind_active_projected_fields()
        _natural_constructor_segments.resume(object_id, sv_class_id, owner=instance)
    except BaseException as error:
        _rollback_natural_constructor(instance, object_id, error)
        raise


def _complete_natural_constructor_portion(instance: Any, object_id: int, python_class_id: str) -> None:
    """Retire an early reservation as its original Python portions finish."""
    pending = _pending_python_root.get()
    if pending is None or pending.instance is not instance or pending.object_id != object_id:
        pending = _reserved_python_receivers.get(object_id)
    if pending is None:
        initialized = getattr(instance, '_svx_initialized_python_portions', None)
        remaining = getattr(instance, '_svx_pending_python_portions', ())
        if initialized is None:
            return
        if not remaining or remaining[0] != python_class_id:
            raise SVXInheritanceError("natural constructor portions completed out of order")
        initialized.add(python_class_id)
        remaining = remaining[1:]
        instance._svx_pending_python_portions = remaining
        instance._svx_pending_python_target_id = remaining[0] if remaining else None
        return
    if pending.instance is not instance or pending.retired:
        raise SVXInheritanceError("natural constructor reservation differs from its receiver")
    if python_class_id == pending.root_class_id:
        if pending.initialized:
            raise SVXInheritanceError("repeated natural root constructor completion")
        pending.initialized = True
        instance._svx_initialized_python_portions = {python_class_id}
        remaining = pending.python_portions
        instance.__dict__.pop('_svx_reserved_python_receiver', None)
    else:
        remaining = getattr(instance, '_svx_pending_python_portions', ())
        if not pending.initialized or not remaining or remaining[0] != python_class_id:
            raise SVXInheritanceError("natural constructor portions completed out of order")
        instance._svx_initialized_python_portions.add(python_class_id)
        remaining = remaining[1:]
    instance._svx_pending_python_portions = remaining
    instance._svx_pending_python_target_id = remaining[0] if remaining else None
    if not remaining:
        _reserved_python_receivers.pop(object_id, None)


def _dispatch_natural_constructor(object_id: int, method_id: str, payload: bytes) -> bytes:
    """Use the existing synchronous DPI payload bridge for constructor segments."""
    from . import _native
    try:
        route = json.loads(method_id.removeprefix(_NATURAL_CONSTRUCTOR_PREFIX))
    except (ValueError, TypeError) as error:
        raise SVXInheritanceError("invalid natural constructor route") from error
    if (not isinstance(route, dict) or set(route) != {"phase", "python", "sv"}
            or route["phase"] not in {"prepare", "resume"}
            or not isinstance(route["python"], str) or not route["python"].startswith("py://")
            or not isinstance(route["sv"], str) or not route["sv"].startswith("sv://")):
        raise SVXInheritanceError("invalid natural constructor route")
    source = _python_subclasses.get(route["python"])
    if source is None:
        raise SVXInheritanceError("natural constructor Python source is not registered")
    instance = _native.inheritance_get(object_id)
    if instance is None and route["phase"] == "prepare":
        from .declarations import SVMirror

        instance = source.__new__(source)
        if not isinstance(instance, source):
            raise SVXInheritanceError("natural constructor allocation returned a different receiver type")
        SVMirror.__init__(instance)
        instance._svx_bind_remote_object(object_id)
        try:
            bind_instance(object_id, instance)
            return _prepare_natural_constructor(instance, object_id, route["python"], route["sv"], payload)
        except BaseException as error:
            SVMirror._svx_retire_failed_python_companion(instance, error)
            raise
    if instance is None or not isinstance(instance, source):
        raise SVXInheritanceError("natural constructor has no reserved Python receiver")
    if route["phase"] == "prepare":
        return _prepare_natural_constructor(instance, object_id, route["python"], route["sv"], payload)
    if payload:
        raise SVXInheritanceError("constructor resumption does not accept new arguments")
    _resume_natural_constructor(instance, object_id, route["sv"])
    _complete_natural_constructor_portion(instance, object_id, route["python"])
    return b""


def _shutdown_python_state() -> None:
    """Clear generated contracts and factories at the simulator boundary."""

    _method_contracts.clear()
    _constructor_contracts.clear()
    _python_subclasses.clear()
    _python_static_methods.clear()
    _python_static_sources.clear()
    _external_handle_targets.clear()
    _vif_views.clear()
    _reserved_python_receivers.clear()


def _register_python_static_source(class_id: str, symbol: str, method_ids: tuple[str, ...]) -> None:
    if (not isinstance(symbol, str) or '.' not in symbol or not isinstance(method_ids, tuple)
            or not all(isinstance(method, str) and method.startswith(class_id + '#') for method in method_ids)):
        raise SVXInheritanceError('invalid declared Python static source')
    declaration = (symbol, method_ids)
    previous = _python_static_sources.get(class_id)
    if previous is not None and previous != declaration:
        raise SVXInheritanceError(f'conflicting Python static source declaration for {class_id}')
    _python_static_sources[class_id] = declaration


def _register_python_static_methods(class_id: str, source: type, method_ids: tuple[str, ...]) -> None:
    pending = {}
    for method_id in method_ids:
        if not method_id.startswith(class_id + "#"):
            raise SVXInheritanceError(f"static method {method_id} does not belong to {class_id}")
        descriptor = inspect.getattr_static(source, method_id.rsplit("#", 1)[1])
        if not isinstance(descriptor, staticmethod):
            raise SVXInheritanceError(f"Python static method {method_id} requires @staticmethod")
        entry = (source, descriptor.__func__)
        existing = _python_static_methods.get(method_id)
        if existing is not None and existing != entry:
            raise SVXInheritanceError(f"conflicting Python static source for {method_id}")
        pending[method_id] = entry
    _python_static_methods.update(pending)


def register_vif_view(target_type_name: str, view_type: type) -> None:
    """Register one generated Python view for a statically typed VIF target."""

    if not isinstance(target_type_name, str) or not target_type_name.startswith("sv-vif://"):
        raise SVXInheritanceError("generated VIF view target must use sv-vif://")
    if not isinstance(view_type, type):
        raise SVXInheritanceError("generated VIF view must be a class")
    existing = _vif_views.get(target_type_name)
    if existing is not None and existing is not view_type:
        raise SVXInheritanceError(
            f"conflicting generated VIF views for {target_type_name}: "
            f"{existing.__module__}.{existing.__name__} and {view_type.__module__}.{view_type.__name__}"
        )
    _vif_views[target_type_name] = view_type


def _decode_vif_view(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_vif_view(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_decode_vif_view(item) for item in value)
    if isinstance(value, dict):
        return {key: _decode_vif_view(item) for key, item in value.items()}
    target_type_name = getattr(value, "target_type_name", None)
    view_type = _vif_views.get(target_type_name)
    if view_type is None and isinstance(target_type_name, str):
        # Generated views use a deterministic module path. Load it before an
        # inbound call reaches user code, rather than requiring a ceremonial
        # import solely to activate an annotated VIF parameter.
        match = re.fullmatch(
            r"sv-vif://([A-Za-z_][A-Za-z0-9_$]*)/([A-Za-z_][A-Za-z0-9_$]*)",
            target_type_name,
        )
        if match is not None:
            interface, modport = match.groups()
            importlib.import_module(f"svx_vif.{interface}.{modport}")
            view_type = _vif_views.get(target_type_name)
    return view_type(value) if view_type is not None and getattr(value, "object_number", 0) != 0 else value


def _encode_vif_view(value: Any) -> Any:
    if isinstance(value, list):
        return [_encode_vif_view(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_encode_vif_view(item) for item in value)
    if isinstance(value, dict):
        return {key: _encode_vif_view(item) for key, item in value.items()}
    target_type_name = getattr(value, "_svx_vif_target_type_name", None)
    if target_type_name is None:
        return value
    reference = getattr(value, "_svx_remote_reference", None)
    if getattr(reference, "target_type_name", None) != target_type_name:
        raise SVXInheritanceError("virtual-interface view has no matching RemoteRef")
    return reference


def register_contract(contract: dict[str, dict[str, Any]]) -> None:
    """Register generated method signatures used by the Python dispatch adapter.

    Each type is a declarative public SvTypes reference plus its immutable wire
    descriptor. No source expression is evaluated.
    """

    for method_id, signature in contract.items():
        if not isinstance(signature, dict):
            raise SVXInheritanceError(
                f"generated call contract {method_id} must contain parameters, request, and response"
            )
        # Generated artifacts from the response-record era did not retain the
        # complete formal ordering. Keep them executable while all newly
        # emitted artifacts use the full prototype contract below.
        if set(signature) == {"request", "response"}:
            request = signature["request"]
            response = signature["response"]
            if not isinstance(request, tuple) or not isinstance(response, tuple):
                raise SVXInheritanceError(
                    f"generated call contract {method_id} must contain tuple request and response fields"
                )
            request_names = {field[0] for field in request if isinstance(field, tuple) and field}
            signature = {
                "parameters": tuple(
                    (name, "inout" if name in {item[0] for item in response if isinstance(item, tuple) and item} else "input", spec)
                    for name, spec in request
                )
                + tuple((name, "output", spec) for name, spec in response if name != "result" and name not in request_names),
                "request": request,
                "response": response,
            }
        timing = signature.get("timing", "task")
        if timing not in {"task", "function"}:
            raise SVXInheritanceError(f"invalid generated timing for {method_id}")
        signature_keys = set(signature) - {"timing"}
        if signature_keys not in (
            {"parameters", "request", "response"},
            {"parameters", "request", "response", "external_targets"},
        ):
            raise SVXInheritanceError(
                f"generated call contract {method_id} must contain parameters, request, and response"
            )
        external_targets = signature.get("external_targets", ())
        if not isinstance(external_targets, tuple) or not all(
            isinstance(target, str) and target for target in external_targets
        ):
            raise SVXInheritanceError(
                f"generated call contract {method_id} external targets must be a tuple of strings"
            )
        _external_handle_targets.update(external_targets)
        normalized = _CallContract(
            _normalize_call_parameters(method_id, signature["parameters"]),
            _normalize_call_fields(method_id, "request", signature["request"]),
            _normalize_call_fields(method_id, "response", signature["response"]),
            timing=timing,
        )
        existing = _method_contracts.get(method_id)
        if existing is not None and existing != normalized:
            raise SVXInheritanceError(f"conflicting SvTypes contract for {method_id}")
        if existing is None:
            _method_contracts[method_id] = normalized


def _normalize_call_parameters(
    method_id: str,
    parameters: tuple[tuple[str, str, dict[str, Any]], ...],
) -> tuple[tuple[str, str, dict[str, Any]], ...]:
    if not isinstance(parameters, tuple):
        raise SVXInheritanceError(
            f"generated call {method_id} parameters must be a tuple"
        )
    normalized: list[tuple[str, str, dict[str, Any]]] = []
    for index, parameter in enumerate(parameters):
        if (
            not isinstance(parameter, tuple)
            or len(parameter) != 3
            or not isinstance(parameter[0], str)
            or not parameter[0]
            or parameter[1] not in {"input", "output", "inout"}
            or not isinstance(parameter[2], dict)
        ):
            raise SVXInheritanceError(
                f"generated call {method_id} parameter {index} is invalid"
            )
        _svtypes_codec(parameter[2])
        normalized.append(parameter)
    names = [name for name, _, _ in normalized]
    if len(names) != len(set(names)):
        raise SVXInheritanceError(
            f"generated call {method_id} contains duplicate parameter names"
        )
    return tuple(normalized)


def _normalize_call_fields(
    method_id: str,
    kind: str,
    fields: tuple[tuple[str, dict[str, Any]], ...],
) -> tuple[tuple[str, dict[str, Any]], ...]:
    if not isinstance(fields, tuple):
        raise SVXInheritanceError(
            f"generated call {method_id} {kind} fields must be a tuple"
        )
    normalized: list[tuple[str, dict[str, Any]]] = []
    for index, field in enumerate(fields):
        if (
            not isinstance(field, tuple)
            or len(field) != 2
            or not isinstance(field[0], str)
            or not field[0]
            or not isinstance(field[1], dict)
        ):
            raise SVXInheritanceError(
                f"generated call {method_id} {kind} field {index} is invalid"
            )
        _svtypes_codec(field[1])
        normalized.append(field)
    names = [name for name, _ in normalized]
    if len(names) != len(set(names)):
        raise SVXInheritanceError(
            f"generated call {method_id} {kind} contains duplicate field names"
        )
    return tuple(normalized)


def _call_record_type_id(method_id: str, kind: str) -> str:
    digest = hashlib.sha256(method_id.encode("utf-8")).hexdigest()
    return f"svx.call.{digest}.{kind}"


def _call_record_class_name(method_id: str, kind: str) -> str:
    return "SVXCall_" + hashlib.sha256(
        f"{method_id}:{kind}".encode("utf-8")
    ).hexdigest()[:20] + "_" + kind.title()


def _call_record_schema(
    method_id: str,
    kind: str,
    fields: tuple[tuple[str, dict[str, Any]], ...],
):
    if not fields:
        return None
    import svtypes

    schema_type = getattr(svtypes, "RecordSchema", None)
    if schema_type is None:
        raise SVXInheritanceError(
            "SvTypes 1.0 generated-call contract is unavailable: "
            "missing public RecordSchema"
        )
    codecs = tuple((name, _svtypes_codec(spec)) for name, spec in fields)
    record_id = _call_record_type_id(method_id, kind)
    class_name = _call_record_class_name(method_id, kind)
    try:
        schema = schema_type(
            unified_type_name=record_id,
            fields=codecs,
            class_name=class_name,
        )
    except TypeError:
        # Compatibility with early RecordSchema implementations that did not
        # accept the optional deterministic class name.
        schema = schema_type(unified_type_name=record_id, fields=codecs)
    except Exception as error:
        raise SVXInheritanceError(
            f"cannot construct SvTypes {kind} record for {method_id}: {error}"
        ) from error
    value_type = getattr(schema, "value_type", None)
    if value_type is None:
        build = getattr(schema, "build", None)
        if not callable(build):
            raise SVXInheritanceError(
                f"SvTypes RecordSchema for {method_id} does not provide build()"
            )
        value_type = build()
    if not isinstance(value_type, type):
        raise SVXInheritanceError(
            f"SvTypes RecordSchema for {method_id} does not expose value_type"
        )
    _validate_call_record_members(value_type, tuple(name for name, _ in fields), method_id, kind)
    if callable(getattr(schema, "pack", None)) and callable(
        getattr(schema, "unpack", None)
    ):
        return schema
    return _RecordSchemaAdapter(schema, value_type)


def _contract_schema(contract: _CallContract, method_id: str, kind: str):
    attribute = f"{kind}_schema"
    schema = getattr(contract, attribute)
    if schema is None:
        fields = getattr(contract, f"{kind}_fields")
        schema = _call_record_schema(method_id, kind, fields)
        setattr(contract, attribute, schema)
    return schema


def register_constructor(
    class_id: str,
    fields: tuple[tuple[str, dict[str, Any]], ...],
    *,
    external_targets: tuple[str, ...] = (),
) -> None:
    if not isinstance(external_targets, tuple) or not all(isinstance(target, str) and target for target in external_targets):
        raise SVXInheritanceError(f"generated constructor {class_id} external targets must be a tuple of strings")
    normalized = _CallContract(
        (),
        _normalize_call_fields(class_id, "constructor", fields), ()
    )
    existing = _constructor_contracts.get(class_id)
    if existing is not None and existing != normalized:
        raise SVXInheritanceError(f"conflicting SvTypes constructor contract for {class_id}")
    if existing is None:
        _constructor_contracts[class_id] = normalized
    _external_handle_targets.update(external_targets)


def register_python_subclass(class_id: str, subclass: type) -> None:
    existing = _python_subclasses.get(class_id)
    if existing is not None and existing is not subclass:
        raise SVXInheritanceError(
            f"multiple Python subclasses registered for {class_id}: "
            f"{existing.__module__}.{existing.__name__} and {subclass.__module__}.{subclass.__name__}"
        )
    _python_subclasses[class_id] = subclass


def _svtypes_codec(spec: dict[str, Any]):
    import svtypes

    try:
        codec = _codec_from_spec(spec)
        descriptor = svtypes.encoding_descriptor(codec).to_dict()
    except Exception as error:
        raise SVXInheritanceError(
            f"cannot construct declared SvTypes codec {spec!r}: {error}"
        ) from error
    if descriptor != spec.get("encoding_descriptor"):
        raise SVXInheritanceError(
            f"SvTypes encoding descriptor changed for {spec.get('unified_type_name')!r}"
        )
    return codec


def _validate_remote_ref_target(target_type_name: str, value: Any) -> None:
    import svtypes

    remote_value_type = getattr(svtypes, "RemoteRefValue", None)
    if value is None:
        object_id = 0
    elif isinstance(value, int):
        if value < 0 or value >= (1 << 64):
            raise SVXInheritanceError(f"foreign object id is outside uint64: {value}")
        object_id = value
    elif remote_value_type is not None and isinstance(value, remote_value_type):
        if value.target_type_name != target_type_name:
            raise SVXInheritanceError(
                "foreign object reference target mismatch: "
                f"expected {target_type_name!r}, got {value.target_type_name!r}"
            )
        object_id = value.object_number
    else:
        raise SVXInheritanceError(
            "RemoteRef value must be None, an object ID, or a public RemoteRefValue"
        )
    if object_id == 0:
        return
    # Externally owned SV class and virtual-interface handles are resolved by
    # their generated typed SV endpoint. Python deliberately has no simulator
    # pointer lookup for them, so it validates only the public RemoteRef target
    # and defers liveness/type resolution to that endpoint.
    if target_type_name in _external_handle_targets:
        return
    from . import _native

    instance = _native.inheritance_get(object_id)
    if instance is None:
        raise SVXInheritanceError(
            f"unknown or stale foreign object id {object_id}"
        )
    declared_ids = getattr(instance, "__svx_foreign_class_ids__", None)
    if declared_ids is None:
        single = getattr(instance, "__svx_foreign_class_id__", None)
        declared_ids = (single,) if single is not None else ()
    if target_type_name not in declared_ids:
        raise SVXInheritanceError(
            "foreign object type mismatch: "
            f"reference requires {target_type_name!r}, object "
            f"{object_id} provides {sorted(declared_ids)!r}"
        )


def _validate_remote_refs(codec: Any, value: Any) -> None:
    """Resolve every opaque reference described by the public SvTypes schema."""

    import svtypes

    try:
        schema = svtypes.schema_descriptor(codec).to_dict()["schema"]
    except Exception as error:
        raise SVXInheritanceError(
            f"cannot inspect SvTypes schema for nested RemoteRef validation: {error}"
        ) from error

    def visit(node: dict[str, Any], item: Any, seen: set[int]) -> None:
        kind = node.get("kind")
        if kind == "remote_ref":
            _validate_remote_ref_target(str(node["target_type_name"]), item)
            return
        if item is None:
            return
        if kind == "object_ref":
            visit(svtypes.schema_descriptor(item).to_dict()["schema"], item, seen)
            return
        if kind in {"object", "struct"}:
            identity = id(item)
            if identity in seen:
                return
            seen.add(identity)
            for field in node.get("fields", []):
                member = getattr(item, field["name"])
                try:
                    field_value = member.value
                except AttributeError:
                    field_value = member
                visit(field["type"], field_value, seen)
            return
        if kind in {"array", "queue", "dyn_array"}:
            elements = item.value if hasattr(item, "value") else item
            for element in elements:
                visit(node["element"], element, seen)
            return
        if kind == "assoc_array":
            elements = item.value if hasattr(item, "value") else item
            for key, element in elements.items():
                visit(node["key"], key, seen)
                visit(node["value"], element, seen)

    visit(schema, value, set())


def _record_value(schema: Any, fields: tuple[tuple[str, dict[str, Any]], ...], values: dict[str, Any]):
    expected = {name for name, _ in fields}
    supplied = set(values)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise TypeError("invalid generated call fields: " + "; ".join(details))
    normalized_values = {
        name: _encode_vif_view(value) for name, value in values.items()
    }
    for name, spec in fields:
        _validate_remote_refs(_svtypes_codec(spec), normalized_values[name])
    try:
        return schema.value_type(**normalized_values)
    except (AttributeError, TypeError):
        from .runtime import codec_session

        try:
            result = schema.value_type(session=codec_session())
            for name, _ in fields:
                member = getattr(result, name)
                if hasattr(member, "value"):
                    member.value = normalized_values[name]
                else:
                    setattr(result, name, normalized_values[name])
            return result
        except Exception as error:
            raise SVXInheritanceError(
                f"cannot construct SvTypes call record: {error}"
            ) from error


def _record_field(value: Any, name: str) -> Any:
    member = getattr(value, name)
    try:
        return member.value
    except AttributeError:
        return member


def _validate_record_fields(
    value: Any, fields: tuple[tuple[str, dict[str, Any]], ...]
) -> None:
    for name, spec in fields:
        _validate_remote_refs(_svtypes_codec(spec), _record_field(value, name))


def _copyout_holder(direction: str, value: Any, *, where: str):
    """Require the public mutable holder used for SV output/inout formals."""

    from .declarations import Inout, Output

    expected = Inout if direction == "inout" else Output
    if not isinstance(value, expected):
        raise TypeError(f"{where} requires svx.{expected.__name__}")
    if direction == "inout" and not value._svx_copyout_is_set:
        raise TypeError(f"{where} requires an initialized svx.Inout(value)")
    return value


def _call_values(
    contract: _CallContract,
    method_id: str,
    values: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a full Python prototype and extract its request payload."""

    expected = {name for name, _, _ in contract.parameters}
    supplied = set(values)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise TypeError(f"invalid inheritance call {method_id} arguments: " + "; ".join(details))
    request: dict[str, Any] = {}
    holders: dict[str, Any] = {}
    for name, direction, _ in contract.parameters:
        value = _encode_vif_view(values[name])
        if direction == "input":
            request[name] = value
        elif direction == "inout":
            holder = _copyout_holder("inout", value, where=f"inheritance argument {name}")
            request[name] = holder.value
            holders[name] = holder
        else:
            holders[name] = _copyout_holder("output", value, where=f"inheritance argument {name}")
    return request, holders


def _is_call_return_field(contract: _CallContract, name: str) -> bool:
    # 'result' was an older private slot, but it is also a legal formal name.
    return name in {"result", _return_slot_name(p[0] for p in contract.parameters)} and all(
        name != parameter_name for parameter_name, _, _ in contract.parameters
    )


def _consume_call_response(
    contract: _CallContract,
    method_id: str,
    response: Any,
    holders: dict[str, Any],
) -> Any:
    result = None
    for name, _ in contract.response_fields:
        value = _record_field(response, name)
        value = _decode_vif_view(value)
        if _is_call_return_field(contract, name):
            result = value
        else:
            holder = holders.get(name)
            if holder is None:
                raise SVXInheritanceError(
                    f"inheritance response {method_id} supplied unexpected copy-out {name!r}"
                )
            holder.value = value
    return result


def _pack_call_record(schema: Any, value: Any) -> bytes:
    import svtypes
    from .runtime import codec_session

    context = svtypes.PackContext(codec_session())
    try:
        try:
            inspect.signature(schema.pack).bind(value, context)
        except TypeError:
            payload = schema.pack(value)
        else:
            payload = schema.pack(value, context)
    finally:
        _release_record_identity(value, context.session)
    if not isinstance(payload, bytes):
        raise SVXInheritanceError("SvTypes call record pack did not return bytes")
    if len(payload) > MAX_CALL_PAYLOAD_BYTES:
        raise SVXInheritanceError(
            f"inheritance call record has {len(payload)} bytes; resource limit is {MAX_CALL_PAYLOAD_BYTES}"
        )
    return payload


def _unpack_call_record(schema: Any, payload: bytes):
    if len(payload) > MAX_CALL_PAYLOAD_BYTES:
        raise SVXInheritanceError(
            f"inheritance call record has {len(payload)} bytes; resource limit is {MAX_CALL_PAYLOAD_BYTES}"
        )
    import svtypes
    from .runtime import codec_session

    context = svtypes.UnpackContext(codec_session())
    try:
        inspect.signature(schema.unpack).bind(payload, context)
    except TypeError:
        value, consumed = schema.unpack(payload)
    else:
        value, consumed = schema.unpack(payload, context)
    try:
        if consumed != len(payload):
            raise SVXInheritanceError("SvTypes call record payload has trailing bytes")
        if not isinstance(value, schema.value_type):
            raise SVXInheritanceError("SvTypes call record returned an incompatible value")
        return value
    finally:
        _release_record_identity(value, context.session)


def _release_record_identity(value: Any, session: Any) -> None:
    object_id = getattr(value, "svtypes_object_number", 0)
    get = getattr(session, "get", None)
    remove = getattr(session, "remove", None)
    if (
        isinstance(object_id, int)
        and object_id != 0
        and callable(get)
        and callable(remove)
        and get(object_id) is value
    ):
        remove(object_id)


def invoke_sv(object_id: int, method_id: str, values: dict[str, Any]):
    """Invoke an SV method using its generated SvTypes request/response records."""

    contract = _method_contracts.get(method_id)
    if not isinstance(contract, _CallContract):
        raise SVXInheritanceError(
            f"no generated call-record contract registered for {method_id}"
        )
    request_values, holders = _call_values(contract, method_id, values)
    request_schema = _contract_schema(contract, method_id, "request")
    if request_schema is None:
        if request_values:
            raise TypeError(f"method {method_id} has a void request")
        request = b""
    else:
        request = _pack_call_record(
            request_schema,
            _record_value(request_schema, contract.request_fields, request_values),
        )
    payload = call_sv(object_id, method_id, request)
    response_schema = _contract_schema(contract, method_id, "response")
    if response_schema is None:
        if payload:
            raise SVXInheritanceError(
                f"void inheritance method {method_id} returned a payload"
            )
        return None
    response = _unpack_call_record(response_schema, payload)
    _validate_record_fields(response, contract.response_fields)
    return _consume_call_response(contract, method_id, response, holders)


def invoke_sv_static(class_id: str, method_id: str, values: dict[str, Any]):
    """Invoke a static SV method through generated SvTypes call records."""

    contract = _method_contracts.get(method_id)
    if not isinstance(contract, _CallContract):
        raise SVXInheritanceError(
            f"no generated call-record contract registered for {method_id}"
        )
    request_values, holders = _call_values(contract, method_id, values)
    request_schema = _contract_schema(contract, method_id, "request")
    if request_schema is None:
        if request_values:
            raise TypeError(f"method {method_id} has a void request")
        request = b""
    else:
        request = _pack_call_record(
            request_schema,
            _record_value(request_schema, contract.request_fields, request_values),
        )
    payload = call_sv_static(class_id, method_id, request)
    response_schema = _contract_schema(contract, method_id, "response")
    if response_schema is None:
        if payload:
            raise SVXInheritanceError(
                f"void inheritance method {method_id} returned a payload"
            )
        return None
    response = _unpack_call_record(response_schema, payload)
    _validate_record_fields(response, contract.response_fields)
    return _consume_call_response(contract, method_id, response, holders)


def encode_constructor(class_id: str, values: dict[str, Any]) -> bytes:
    """Encode a generated constructor request as one SvTypes record."""

    contract = _constructor_contracts.get(class_id)
    if not isinstance(contract, _CallContract):
        raise SVXInheritanceError(
            f"no generated constructor-record contract registered for {class_id}"
        )
    schema = _contract_schema(contract, class_id, "request")
    if schema is None:
        if values:
            raise TypeError(f"constructor {class_id} has no parameters")
        return b""
    return _pack_call_record(
        schema,
        _record_value(schema, contract.request_fields, values),
    )


@inheritance_boundary('SV -> Python')
def dispatch_python_call(
    object_id: int, method_id: str, payload: bytes, function_context: bool = False
) -> bytes:
    """C++ callback entry point; decode, invoke, and encode only through SvTypes."""

    if function_context:
        from .callback_context import blocking_operations_disallowed

        with blocking_operations_disallowed(f"executing SV function callback {method_id}"):
            return _dispatch_python_call(object_id, method_id, payload)
    return _dispatch_python_call(object_id, method_id, payload)


def _dispatch_python_call(object_id: int, method_id: str, payload: bytes) -> bytes:
    if method_id.startswith(_NATURAL_CONSTRUCTOR_PREFIX):
        from .callback_context import blocking_operations_disallowed
        with blocking_operations_disallowed("executing synchronous cross-language construction"):
            return _dispatch_natural_constructor(object_id, method_id, payload)
    callback_boundary = None
    if method_id.startswith(_PYTHON_CALLBACK_METHOD_PREFIX):
        try:
            route = json.loads(method_id.removeprefix(_PYTHON_CALLBACK_METHOD_PREFIX))
        except (ValueError, TypeError) as error:
            raise SVXInheritanceError('invalid inherited callback route') from error
        if (not isinstance(route, dict) or set(route) != {'boundary', 'method'}
                or not all(isinstance(value, str) and value for value in route.values())):
            raise SVXInheritanceError('invalid inherited callback route')
        callback_boundary, method_id = route['boundary'], route['method']
    python_static = method_id.startswith(_PYTHON_STATIC_METHOD_PREFIX)
    if python_static:
        method_id = method_id.removeprefix(_PYTHON_STATIC_METHOD_PREFIX)
    python_base = method_id.startswith(_PYTHON_BASE_METHOD_PREFIX)
    if python_base:
        method_id = method_id.removeprefix(_PYTHON_BASE_METHOD_PREFIX)
    contract = _method_contracts.get(method_id)
    if contract is None:
        raise SVXInheritanceError(f"no generated SvTypes contract registered for {method_id}")
    from . import _native

    static_method = None
    instance = None
    if python_static:
        if object_id != 0:
            raise SVXInheritanceError("Python static callback must not use an instance ID")
        entry = _python_static_methods.get(method_id)
        if entry is None:
            class_id = method_id.rsplit('#', 1)[0]
            declaration = _python_static_sources.get(class_id)
            if declaration is not None:
                symbol, methods = declaration
                module, name = symbol.rsplit('.', 1)
                source = getattr(importlib.import_module(module), name)
                _register_python_static_methods(class_id, source, methods)
                entry = _python_static_methods.get(method_id)
        if entry is None:
            raise SVXInheritanceError(f"no Python static source registered for {method_id}")
        static_method = entry[1]
    else:
        instance = _native.inheritance_get(object_id)
    if not python_static and instance is None:
        raise SVXInheritanceError(f"unknown Python inheritance object id {object_id}")
    method_name = method_id.rsplit("#", 1)[1]
    base_method = None
    if python_base:
        class_id = method_id.rsplit("#", 1)[0]
        base_class = getattr(type(instance), "__svx_python_base_classes__", {}).get(class_id)
        if not isinstance(base_class, type) or not isinstance(instance, base_class):
            raise SVXInheritanceError(f"no Python base portion registered for {class_id}")
        descriptor = inspect.getattr_static(base_class, method_name)
        base_method = descriptor.__get__(instance, base_class)
    request_schema = _contract_schema(contract, method_id, "request")
    if request_schema is None:
        if payload:
            raise SVXInheritanceError(
                f"void inheritance request {method_id} contains data"
            )
        request_values: dict[str, Any] = {}
    else:
        request = _unpack_call_record(request_schema, payload)
        _validate_record_fields(request, contract.request_fields)
        request_values = {
            name: _decode_vif_view(_record_field(request, name))
            for name, _ in contract.request_fields
        }
    from .declarations import Inout, Output

    arguments: list[Any] = []
    holders: dict[str, Any] = {}
    for name, direction, _ in contract.parameters:
        if direction == "input":
            arguments.append(request_values[name])
        elif direction == "inout":
            holder = Inout(request_values[name])
            holders[name] = holder
            arguments.append(holder)
        else:
            holder = Output()
            holders[name] = holder
            arguments.append(holder)
    foreign_dispatch = getattr(instance, "__svx_dispatch_foreign__", None)
    callback_method = None
    if instance is not None and not python_base:
        portions = getattr(type(instance), "__svx_python_callback_portions__", {})
        portion_id = portions.get(callback_boundary or method_id.rsplit("#", 1)[0])
        if (callback_boundary is not None and portion_id is None
                and callback_boundary != getattr(type(instance), '__svx_foreign_class_id__', None)):
            raise SVXInheritanceError(f'no Python callback boundary registered for {callback_boundary}')
        if portion_id is not None:
            portion_class = getattr(type(instance), "__svx_python_base_classes__", {}).get(portion_id)
            if not isinstance(portion_class, type) or not isinstance(instance, portion_class):
                raise SVXInheritanceError(f"no Python callback portion registered for {portion_id}")
            callback_method = inspect.getattr_static(portion_class, method_name).__get__(instance, portion_class)
    if python_static:
        result = static_method(*arguments)
    elif python_base:
        result = base_method(*arguments)
    elif callback_method is not None:
        result = callback_method(*arguments)
    elif foreign_dispatch:
        result = foreign_dispatch(method_name, *arguments)
    else:
        result = getattr(instance, method_name)(*arguments)
    response_schema = _contract_schema(contract, method_id, "response")
    if response_schema is None:
        if result is not None:
            raise SVXInheritanceError(
                f"void inheritance method {method_id} returned a value"
            )
        return b""
    response_values: dict[str, Any] = {}
    has_result = any(_is_call_return_field(contract, name) for name, _ in contract.response_fields)
    if result is not None and not has_result:
        raise SVXInheritanceError(f"void inheritance method {method_id} returned a value")
    for name, _ in contract.response_fields:
        if _is_call_return_field(contract, name):
            response_values[name] = result
            continue
        holder = holders[name]
        if not holder._svx_copyout_is_set:
            raise SVXInheritanceError(
                f"inheritance method {method_id} did not assign {name!r}"
            )
        response_values[name] = holder.value
    response = _record_value(response_schema, contract.response_fields, response_values)
    return _pack_call_record(response_schema, response)


@inheritance_boundary('SV -> Python construction', identity='class_id')
def create_python_instance(class_id: str, object_id: int, payload: bytes) -> None:
    """DPI factory entry point for an SV-initiated generated pair."""

    from .callback_context import blocking_operations_disallowed

    with blocking_operations_disallowed(f"executing SV constructor {class_id}"):
        if class_id.startswith(_PYTHON_RECEIVER_EXPECT_PREFIX):
            if payload:
                raise SVXInheritanceError("receiver expectation does not accept constructor arguments")
            _expect_python_receiver(class_id.removeprefix(_PYTHON_RECEIVER_EXPECT_PREFIX), object_id)
        elif class_id.startswith(_PYTHON_RECEIVER_RESERVE_PREFIX):
            if payload:
                raise SVXInheritanceError("receiver reservation does not accept constructor arguments")
            _reserve_python_receiver(class_id.removeprefix(_PYTHON_RECEIVER_RESERVE_PREFIX), object_id)
        elif class_id.startswith(_PYTHON_ROOT_INIT_PREFIX):
            _initialize_pending_python_root(class_id.removeprefix(_PYTHON_ROOT_INIT_PREFIX), object_id, payload)
        elif class_id.startswith(_PYTHON_ROOT_ALLOC_PREFIX):
            _allocate_sv_origin_python_root(class_id.removeprefix(_PYTHON_ROOT_ALLOC_PREFIX), object_id, payload)
        elif class_id.startswith(_PYTHON_PORTION_INIT_PREFIX):
            _initialize_sv_origin_python_portion(class_id.removeprefix(_PYTHON_PORTION_INIT_PREFIX), object_id, payload)
        elif class_id.startswith(_SV_CONSTRUCTOR_ARGUMENTS_PREFIX):
            _record_staged_sv_constructor(class_id.removeprefix(_SV_CONSTRUCTOR_ARGUMENTS_PREFIX), object_id, payload)
        else:
            _create_python_instance(class_id, object_id, payload)


@dataclass
class _PendingPythonRoot:
    instance: Any
    root_class_id: str
    object_id: int | None = None
    initialized: bool = False
    python_portions: tuple[str, ...] = ()
    expected_class_id: str | None = None
    expected_object_id: int | None = None
    retired: bool = False
    direct_field_ids: dict[str, str] | None = None


_pending_python_root: ContextVar[_PendingPythonRoot | None] = ContextVar("svx_pending_python_root", default=None)
_reserved_python_receivers: dict[int, _PendingPythonRoot] = {}


def _retire_python_receiver_reservation(instance: Any) -> None:
    """Drop construction-owned references before a native release hook runs."""
    object_id = getattr(instance, '_svx_remote_object_id', None)
    reserved = _reserved_python_receivers.get(object_id)
    if reserved is not None and reserved.instance is instance:
        reserved.retired = True
        del _reserved_python_receivers[object_id]
    pending = _pending_python_root.get()
    if pending is not None and pending.instance is instance and pending.object_id is not None:
        pending.retired = True


def _expect_python_receiver(class_id: str, object_id: int) -> None:
    """Identify a Python-origin allocation before any SV constructor executes."""
    pending = _pending_python_root.get()
    if pending is None:
        return
    if pending.expected_class_id is not None and pending.expected_class_id != class_id:
        raise SVXInheritanceError("receiver expectation differs from the requested SV target")
    if (object_id <= 0 or object_id >= (1 << 64)
            or pending.expected_object_id not in (None, object_id)):
        raise SVXInheritanceError("receiver expectation changed the paired object ID")
    pending.expected_object_id = object_id


def _reserve_python_receiver(selector: str, object_id: int) -> None:
    """Bind an early constructor callback receiver without running user init."""
    from . import _native
    from .declarations import SVMirror

    if not isinstance(object_id, int) or object_id <= 0 or object_id >= (1 << 64):
        raise SVXInheritanceError("receiver reservation requires a nonzero object ID")
    pending = _pending_python_root.get()
    if (pending is not None and pending.direct_field_ids is not None
            and selector == pending.root_class_id
            and pending.expected_object_id in (None, object_id)):
        _bind_pending_direct_receiver(pending, object_id)
        return
    if not selector.startswith(_PYTHON_ROOT_ALLOC_PREFIX):
        _reserve_sv_origin_direct_receiver(selector, object_id)
        return
    try:
        selection = json.loads(selector.removeprefix(_PYTHON_ROOT_ALLOC_PREFIX))
    except (ValueError, TypeError) as error:
        raise SVXInheritanceError("invalid receiver reservation target") from error
    if (not isinstance(selection, dict) or set(selection) != {'root', 'target', 'portions'}
            or not isinstance(selection['root'], str) or not isinstance(selection['target'], str)
            or not isinstance(selection['portions'], list)
            or not all(isinstance(value, str) for value in selection['portions'])):
        raise SVXInheritanceError("invalid receiver reservation target")
    root_id, target_id = selection['root'], selection['target']
    root, target = _python_subclasses.get(root_id), _python_subclasses.get(target_id)
    if root is None or target is None or not issubclass(target, root):
        raise SVXInheritanceError("receiver reservation target does not contain its root")
    portions = tuple(selection['portions'])
    _validate_python_constructor_portions(root_id, portions, target)
    existing = _native.inheritance_get(object_id)
    if existing is not None:
        if getattr(existing, '_svx_reserved_python_receiver', None) != selection:
            raise SVXInheritanceError("receiver reservation object ID is already bound")
        return
    pending = _pending_python_root.get()
    if pending is not None and (
            (pending.expected_object_id is not None and pending.expected_object_id != object_id)
            or (pending.object_id is not None and pending.object_id != object_id)):
        pending = None
    if pending is not None:
        if (pending.root_class_id != root_id or not isinstance(pending.instance, target)
                or pending.python_portions != portions or pending.object_id is not None):
            raise SVXInheritanceError("receiver reservation differs from pending construction")
        instance = pending.instance
    else:
        instance = target.__new__(target)
    if not isinstance(instance, target):
        raise SVXInheritanceError("receiver reservation returned a different receiver type")
    SVMirror.__init__(instance)
    instance._svx_bind_remote_object(object_id)
    bind_instance(object_id, instance)
    try:
        if instance.__svx_root_field_ids__:
            instance._svx_bind_projected_fields(instance.__svx_root_field_ids__)
        instance._svx_reserved_python_receiver = selection
        instance._svx_reserved_owner_prepared = True
        if pending is not None:
            pending.object_id = object_id
        else:
            _reserved_python_receivers[object_id] = _PendingPythonRoot(
                instance, root_id, object_id=object_id, python_portions=portions)
    except BaseException as error:
        SVMirror._svx_retire_failed_python_companion(instance, error)
        raise


def _constructor_argument_fingerprints(class_id: str, values: dict[str, Any]) -> tuple[bytes, ...]:
    """Compare typed values, not record headers with newly allocated object IDs."""
    import svtypes
    from .runtime import codec_session

    contract = _constructor_contracts.get(class_id)
    if contract is None or set(values) != {name for name, _ in contract.request_fields}:
        raise SVXInheritanceError(f'constructor arguments differ from contract for {class_id}')
    fingerprints = []
    for name, spec in contract.request_fields:
        codec = _svtypes_codec(spec)
        value = _encode_vif_view(values[name])
        _validate_remote_refs(codec, value)
        context = svtypes.PackContext(codec_session())
        try:
            inspect.signature(codec.pack).bind(value, context)
        except TypeError:
            payload = codec.pack(value)
        else:
            payload = codec.pack(value, context)
        if not isinstance(payload, bytes):
            raise SVXInheritanceError('constructor value codec did not produce bytes')
        fingerprints.append(payload)
    return tuple(fingerprints)


def _record_staged_sv_constructor(class_id: str, object_id: int, payload: bytes) -> None:
    from . import _native

    instance = _native.inheritance_get(object_id)
    source = _python_subclasses.get(class_id)
    if instance is None or source is None or not isinstance(instance, source):
        raise SVXInheritanceError(f'no staged receiver for constructor {class_id}')
    contract = _constructor_contracts.get(class_id)
    arguments = _decode_constructor_arguments(class_id, payload)
    values = dict(zip((name for name, _ in contract.request_fields), arguments, strict=True))
    fingerprints = _constructor_argument_fingerprints(class_id, values)
    recorded = instance.__dict__.setdefault('_svx_completed_sv_constructor_arguments', {})
    if class_id in recorded:
        raise SVXInheritanceError(f'repeated staged SV constructor {class_id}')
    recorded[class_id] = fingerprints


def _validate_staged_base_constructor(instance: Any, class_id: str, values: dict[str, Any]) -> None:
    if not getattr(instance, '_svx_python_portion_initializing', False):
        return
    recorded = getattr(instance, '_svx_completed_sv_constructor_arguments', {})
    if class_id not in recorded:
        raise SVXInheritanceError(f'no completed SV constructor arguments for {class_id}')
    if _constructor_argument_fingerprints(class_id, values) != recorded[class_id]:
        raise SVXInheritanceError(
            f'staged super constructor arguments differ from completed SV base {class_id}; '
            'independent ancestor constructor routing is not yet implemented')


def _allocate_sv_origin_python_root(selector: str, object_id: int, payload: bytes) -> None:
    """Allocate the final receiver but initialize only its root SV constructor portion."""
    selection = json.loads(selector)
    if not isinstance(selection, dict) or set(selection) not in ({"root", "target"}, {"root", "target", "portions"}):
        raise SVXInheritanceError("invalid Python-root constructor target selector")
    root_id, target_id = selection["root"], selection["target"]
    if not isinstance(root_id, str) or not isinstance(target_id, str):
        raise SVXInheritanceError("invalid Python-root constructor target IDs")
    root, target = _python_subclasses.get(root_id), _python_subclasses.get(target_id)
    if root is None or target is None or not issubclass(target, root):
        raise SVXInheritanceError("Python construction target does not contain its root portion")
    portions = selection.get("portions", [] if root_id == target_id else [target_id])
    if not isinstance(portions, list) or not all(isinstance(portion, str) for portion in portions):
        raise SVXInheritanceError("invalid Python constructor portion list")
    _validate_python_constructor_portions(root_id, tuple(portions), target)
    instance = target.__new__(target)
    if not isinstance(instance, target):
        raise SVXInheritanceError("Python construction target returned a different receiver type")
    pending = _PendingPythonRoot(instance, root_id, python_portions=tuple(portions))
    token = _pending_python_root.set(pending)
    try:
        _initialize_pending_python_root(root_id, object_id, payload)
    except BaseException as error:
        if pending.object_id is not None:
            from .declarations import SVMirror
            SVMirror._svx_retire_failed_python_companion(instance, error)
        raise
    finally:
        _pending_python_root.reset(token)


def _initialize_sv_origin_python_portion(class_id: str, object_id: int, payload: bytes) -> None:
    """Resume the next Python portion after its intervening SV constructor returns."""
    from . import _native
    instance = _native.inheritance_get(object_id)
    target = _python_subclasses.get(class_id)
    if instance is None or target is None or not isinstance(instance, target):
        raise SVXInheritanceError(f"no staged Python receiver registered for {class_id}")
    remaining = getattr(instance, "_svx_pending_python_portions", ())
    if (not remaining or remaining[0] != class_id
            or getattr(instance, "_svx_python_portion_initializing", False)):
        raise SVXInheritanceError("unexpected or repeated Python constructor portion")
    # Consume the stage before entering user code, including any reentrant call.
    instance._svx_pending_python_target_id = None
    instance._svx_python_portion_initializing = True
    try:
        arguments = _decode_constructor_arguments(class_id, payload)
        target.__init__(instance, *arguments)
        instance._svx_initialized_python_portions.add(class_id)
        instance._svx_pending_python_portions = remaining[1:]
        instance._svx_pending_python_target_id = remaining[1] if len(remaining) > 1 else None
    except BaseException as error:
        from .declarations import SVMirror
        SVMirror._svx_retire_failed_python_companion(instance, error)
        raise
    finally:
        instance._svx_python_portion_initializing = False


def _validate_python_constructor_portions(root_id: str, portions: tuple[str, ...], target: type) -> None:
    expected = target.__dict__.get("__svx_constructor_python_portions__")
    if expected is not None and expected != portions:
        raise SVXInheritanceError("Python constructor portions differ from the generated target plan")
    if root_id in portions or len(set(portions)) != len(portions):
        raise SVXInheritanceError("duplicate Python constructor portion")
    previous = _python_subclasses.get(root_id)
    for class_id in portions:
        portion = _python_subclasses.get(class_id)
        if (portion is None or previous is None or class_id not in _constructor_contracts
                or not issubclass(portion, previous) or not issubclass(target, portion)):
            raise SVXInheritanceError("Python constructor portions do not follow the receiver lineage")
        previous = portion


def _decode_constructor_arguments(class_id: str, payload: bytes) -> tuple[Any, ...]:
    contract = _constructor_contracts.get(class_id)
    if contract is None:
        raise SVXInheritanceError(f"no generated constructor contract registered for {class_id}")
    schema = _contract_schema(contract, class_id, "request")
    if schema is None:
        if payload:
            raise SVXInheritanceError(f"void constructor request {class_id} contains data")
        return ()
    request = _unpack_call_record(schema, payload)
    _validate_record_fields(request, contract.request_fields)
    return tuple(_decode_vif_view(_record_field(request, name)) for name, _ in contract.request_fields)


def _create_sv_with_python_root(instance: Any, root_class_id: str, class_id: str, payload: bytes,
                                *, python_portions: tuple[str, ...] = ()) -> int:
    """Construct an SV target while its base constructor initializes this owner."""
    from . import _native

    if getattr(instance, "_svx_remote_object_id", None) is not None:
        raise SVXInheritanceError("Python-root construction receiver is already bound")
    _validate_python_constructor_portions(root_class_id, python_portions, type(instance))
    pending = _PendingPythonRoot(instance, root_class_id, python_portions=python_portions,
                                 expected_class_id=class_id)
    token = _pending_python_root.set(pending)
    created_id = None
    try:
        created_id = _native.inheritance_create_sv(class_id, payload)
        if not pending.initialized or pending.object_id != created_id:
            raise SVXInheritanceError("SV target did not initialize the expected Python-root owner")
        if getattr(instance, "_svx_pending_python_portions", ()):
            raise SVXInheritanceError("SV target did not initialize all Python constructor portions")
        instance._svx_target_constructor_completed = True
        return created_id
    except BaseException as error:
        from .declarations import SVMirror

        object_ids = tuple(dict.fromkeys(object_id for object_id in (pending.object_id, created_id) if object_id is not None))
        if object_ids:
            for action, cleanup in (
                ("close projected storage", lambda: SVMirror._svx_release_projected_fields(instance)),
                *((f"close failed SV target {object_id}", lambda object_id=object_id: _native.inheritance_close(object_id))
                  for object_id in object_ids),
            ):
                try:
                    cleanup()
                except BaseException as cleanup_error:
                    error.add_note(f"construction could not {action}: {cleanup_error}")
        raise
    finally:
        _pending_python_root.reset(token)


def _bind_pending_direct_receiver(pending: _PendingPythonRoot, object_id: int) -> None:
    from . import _native

    if pending.retired:
        raise SVXInheritanceError('direct mirror constructor receiver was retired')
    if pending.object_id is not None:
        if pending.object_id != object_id or _native.inheritance_get(object_id) is not pending.instance:
            raise SVXInheritanceError('direct mirror constructor changed its receiver binding')
        return
    pending.object_id = object_id
    pending.instance._svx_bind_remote_object(object_id)
    bind_instance(object_id, pending.instance)
    if pending.direct_field_ids:
        pending.instance._svx_bind_projected_fields(pending.direct_field_ids)


def _reserve_sv_origin_direct_receiver(class_id: str, object_id: int) -> None:
    from . import _native
    from .declarations import SVMirror

    target = _python_subclasses.get(class_id)
    fields = target.__dict__.get('__svx_direct_mirror_field_ids__') if target is not None else None
    if (not class_id.startswith('sv://') or not isinstance(fields, dict)
            or target.__dict__.get('__svx_foreign_class_id__') != class_id):
        raise SVXInheritanceError('receiver reservation requires a generated constructor target')
    existing = _native.inheritance_get(object_id)
    if existing is not None:
        reserved = _reserved_python_receivers.get(object_id)
        if (reserved is not None and reserved.instance is existing
                and reserved.root_class_id == class_id and reserved.direct_field_ids == fields):
            return
        raise SVXInheritanceError('literal receiver reservation object ID is already bound')
    instance = target.__new__(target)
    if not isinstance(instance, target):
        raise SVXInheritanceError('literal receiver reservation returned a different receiver type')
    SVMirror.__init__(instance)
    pending = _PendingPythonRoot(instance, class_id, expected_object_id=object_id,
                                 direct_field_ids=dict(fields))
    try:
        _bind_pending_direct_receiver(pending, object_id)
        _reserved_python_receivers[object_id] = pending
    except BaseException as error:
        SVMirror._svx_retire_failed_python_companion(instance, error)
        raise


def _create_sv_with_direct_mirror(instance: Any, class_id: str, payload: bytes,
                                  field_ids: dict[str, str]) -> int:
    """Resume the existing Python constructor around allocation of only its SV base."""
    from . import _native
    from .declarations import SVMirror

    if getattr(instance, '_svx_remote_object_id', None) is not None:
        raise SVXInheritanceError('direct mirror construction receiver is already bound')
    pending = _PendingPythonRoot(instance, class_id, expected_class_id=class_id,
                                 direct_field_ids=dict(field_ids))
    token = _pending_python_root.set(pending)
    created_id = None
    try:
        created_id = _native.inheritance_create_sv(class_id, payload)
        if pending.retired or not pending.initialized or pending.object_id != created_id:
            raise SVXInheritanceError('SV base did not complete the direct mirror receiver binding')
        instance._svx_target_constructor_completed = True
        return created_id
    except BaseException as error:
        object_ids = tuple(dict.fromkeys(value for value in (pending.object_id, created_id) if value is not None))
        if object_ids:
            for action, cleanup in (
                ('close projected storage', lambda: SVMirror._svx_release_projected_fields(instance)),
                *((f'close failed SV base {value}', lambda value=value: _native.inheritance_close(value))
                  for value in object_ids),
            ):
                try:
                    cleanup()
                except BaseException as cleanup_error:
                    error.add_note(f'construction could not {action}: {cleanup_error}')
        raise
    finally:
        _pending_python_root.reset(token)


def _initialize_pending_python_root(class_id: str, object_id: int, payload: bytes) -> None:
    pending = _pending_python_root.get()
    if pending is not None and pending.object_id == object_id and pending.retired:
        raise SVXInheritanceError('constructor receiver was retired before initialization completed')
    if (pending is not None and pending.direct_field_ids is not None
            and pending.expected_object_id in (None, object_id)):
        if class_id != pending.root_class_id:
            raise SVXInheritanceError('direct mirror constructor selected a different SV base')
        _bind_pending_direct_receiver(pending, object_id)
        pending.initialized = True
        return
    # A supplied ID without an active Python-origin factory retains the normal
    # existing-handle path: it must not allocate another companion.
    if (pending is None
            or (pending.expected_object_id is not None and pending.expected_object_id != object_id)
            or (pending.object_id is not None and pending.object_id != object_id)):
        pending = _reserved_python_receivers.pop(object_id, None)
        if pending is None and class_id.startswith(_PYTHON_ROOT_ALLOC_PREFIX):
            raise SVXInheritanceError('reserved constructor receiver is retired or missing')
        if pending is None:
            target = _python_subclasses.get(class_id)
            if target is not None and '__svx_direct_mirror_field_ids__' in target.__dict__:
                from . import _native

                if _native.inheritance_get(object_id) is None:
                    raise SVXInheritanceError('literal constructor receiver is retired or missing')
        if pending is not None:
            instance = pending.instance
            token = _pending_python_root.set(pending)
            try:
                _initialize_pending_python_root(class_id, object_id, payload)
            except BaseException as error:
                from .declarations import SVMirror
                SVMirror._svx_retire_failed_python_companion(instance, error)
                raise
            finally:
                _pending_python_root.reset(token)
        return
    if class_id.startswith(_PYTHON_ROOT_ALLOC_PREFIX):
        try:
            selection = json.loads(class_id.removeprefix(_PYTHON_ROOT_ALLOC_PREFIX))
        except (ValueError, TypeError) as error:
            raise SVXInheritanceError('invalid pending constructor target selector') from error
        if (not isinstance(selection, dict) or set(selection) != {'root', 'target', 'portions'}
                or selection['target'] != getattr(type(pending.instance), '__svx_foreign_class_id__', None)
                or selection['portions'] != list(pending.python_portions)):
            raise SVXInheritanceError('pending constructor selector differs from receiver plan')
        class_id = selection['root']
    reserved = getattr(pending.instance, '_svx_reserved_python_receiver', None)
    if (pending.root_class_id != class_id or pending.initialized
            or (pending.object_id is not None and (reserved is None or pending.object_id != object_id))):
        raise SVXInheritanceError("unexpected or repeated Python-root constructor portion")
    contract = _constructor_contracts.get(class_id)
    root = _python_subclasses.get(class_id)
    if contract is None or root is None or not isinstance(pending.instance, root):
        raise SVXInheritanceError(f"no matching Python-root construction portion for {class_id}")
    instance = pending.instance
    if reserved is None:
        instance._svx_bind_remote_object(object_id)
        bind_instance(object_id, instance)
    else:
        del instance._svx_reserved_python_receiver
    pending.object_id = object_id
    try:
        arguments = _decode_constructor_arguments(class_id, payload)
        root.__init__(instance, *arguments)
        if pending.retired:
            raise SVXInheritanceError('constructor receiver was retired during initialization')
        if not getattr(instance, "_svx_root_owner_initialized", False):
            raise SVXInheritanceError("Python-root constructor did not initialize its owner")
    except BaseException as error:
        _rollback_natural_constructor(instance, object_id, error)
        raise
    pending.initialized = True
    instance._svx_initialized_python_portions = {class_id}
    instance._svx_pending_python_portions = pending.python_portions
    instance._svx_pending_python_target_id = pending.python_portions[0] if pending.python_portions else None


def _create_python_instance(class_id: str, object_id: int, payload: bytes) -> None:

    contract = _constructor_contracts.get(class_id)
    subclass = _python_subclasses.get(class_id)
    if contract is None or subclass is None:
        raise SVXInheritanceError(f"no generated Python factory registered for {class_id}")
    schema = _contract_schema(contract, class_id, "request")
    if schema is None:
        if payload:
            raise SVXInheritanceError(
                f"void constructor request {class_id} contains data"
            )
        arguments = ()
    else:
        request = _unpack_call_record(schema, payload)
        _validate_record_fields(request, contract.request_fields)
        arguments = tuple(
            _decode_vif_view(_record_field(request, name)) for name, _ in contract.request_fields
        )
    creator = getattr(subclass, "__svx_create_from_sv__", None)
    if creator is None:
        raise SVXInheritanceError(f"generated Python subclass factory is missing for {class_id}")
    creator(object_id, *arguments)
