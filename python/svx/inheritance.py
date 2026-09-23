"""Manifest, mirrors, and SvTypes-backed cross-language inheritance dispatch."""

from __future__ import annotations

from dataclasses import dataclass
import ast
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any, Generic, Protocol, TypeVar

from .errors import SVXInheritanceError, SVXReadonlyRefError, SVXRemoteError, SVXStaleRefError
from ._svtypes_contract import SVTYPES_REQUIRED_CAPABILITIES


SCHEMA_URI = "https://svx.dev/schema/inheritance-manifest/v2"
SCHEMA_VERSION = "2.0.0"
GENERATOR_ABI_VERSION = 2
REQUIRED_RUNTIME_CAPABILITIES = SVTYPES_REQUIRED_CAPABILITIES
EXTERNAL_FIELD_STORAGE_CAPABILITY = "svtypes.external-field-storage.v1"
MAX_CALL_PAYLOAD_BYTES = 16 * 1024 * 1024
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
_RefValue = TypeVar("_RefValue")


class _RefEndpoint(Protocol[_RefValue]):
    """Internal synchronous endpoint used by generated ref helpers/portals."""

    def read(self) -> _RefValue: ...

    def write(self, value: _RefValue) -> None: ...


class Ref(Generic[_RefValue]):
    """A typed, optionally call-scoped cross-language SystemVerilog ref.

    A standalone Ref retains its supplied value. Generated invocation code
    temporarily binds it to a typed helper or portal; a borrowed portal becomes
    stale when closed, while a caller-owned helper retains its final value.
    """

    def __init__(self, value: _RefValue | None = None) -> None:
        self._value = value
        self._endpoint: _RefEndpoint[_RefValue] | None = None
        self._readonly = False
        self._stale = False
        self._borrowed = False

    @property
    def value(self) -> _RefValue | None:
        if self._stale:
            raise SVXStaleRefError("SVX ref is no longer active")
        if self._endpoint is not None:
            return self._endpoint.read()
        return self._value

    @value.setter
    def value(self, value: _RefValue) -> None:
        if self._stale:
            raise SVXStaleRefError("SVX ref is no longer active")
        if self._readonly:
            raise SVXReadonlyRefError("cannot assign through a const ref")
        if self._endpoint is not None:
            self._endpoint.write(value)
        else:
            self._value = value

    def _bind(
        self,
        endpoint: _RefEndpoint[_RefValue],
        *,
        readonly: bool = False,
        borrowed: bool = False,
    ) -> None:
        if self._endpoint is not None or self._stale:
            raise SVXInheritanceError("Ref is already bound or stale")
        self._endpoint = endpoint
        self._readonly = readonly
        self._borrowed = borrowed

    def _close(self, *, retain_value: bool) -> None:
        if self._endpoint is not None and retain_value:
            self._value = self._endpoint.read()
        self._endpoint = None
        self._readonly = False
        if self._borrowed or not retain_value:
            self._stale = True

@dataclass(frozen=True)
class TypeBinding:
    """One immutable public SvTypes declaration and generated SV adapter."""

    unified_type_name: str
    python_module: str
    python_symbol: str
    python_args: tuple[Any, ...]
    python_kwargs: tuple[tuple[str, Any], ...]
    sv: str
    sv_packer: str
    encoding_descriptor: tuple[tuple[str, Any], ...]

    def runtime_spec(self) -> dict[str, Any]:
        return {
            "unified_type_name": self.unified_type_name,
            "python": {
                "module": self.python_module,
                "symbol": self.python_symbol,
                "args": list(self.python_args),
                "kwargs": dict(self.python_kwargs),
            },
            "encoding_descriptor": dict(self.encoding_descriptor),
        }


@dataclass(frozen=True)
class Parameter:
    name: str
    type_binding: TypeBinding
    direction: str
    # ``readonly`` is the cross-language spelling of SV ``const ref``. It is
    # meaningful only when direction is ``ref``.
    ref_access: str = "readwrite"


@dataclass(frozen=True)
class Method:
    canonical_id: str
    name: str
    parameters: tuple[Parameter, ...]
    return_type: TypeBinding | None
    timing: str
    virtual: bool
    pure_virtual: bool


@dataclass(frozen=True)
class Constructor:
    initiator: str
    parameters: tuple[Parameter, ...]


@dataclass(frozen=True)
class Field:
    """One directly declared, schema-backed instance field."""

    name: str
    type_binding: TypeBinding


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
        """Stable helper name; concrete specializations cannot collide."""

        if self.specialization is None:
            return self.name
        digest = hashlib.sha256(
            json.dumps(_specialization_dict(self.specialization), sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return f"{self.name}__svx_{digest}"


@dataclass(frozen=True)
class Manifest:
    schema_uri: str
    schema_version: str
    generator_abi_version: int
    required_runtime_capabilities: tuple[str, ...]
    classes: tuple[ForeignClass, ...]


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
    if not callable(getattr(codec, "pack", None)) or not callable(
        getattr(codec, "unpack", None)
    ):
        raise SVXInheritanceError(
            f"SvTypes declaration {module_name}:{symbol} does not provide pack/unpack"
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
    return {
        "python": {
            "module": module_name,
            "symbol": symbol,
            "args": args,
            "kwargs": kwargs,
        }
    }


def _migrate_type_binding(value: Any, where: str) -> Any:
    if value == "void":
        return value
    if isinstance(value, str) and value in _LEGACY_TYPES:
        value = _LEGACY_TYPES[value]
    if not isinstance(value, dict) or "svtypes" not in value:
        return value
    expression = value.get("svtypes")
    if not isinstance(expression, str):
        raise _error(where, "legacy svtypes expression must be a string")
    spec = _legacy_expression_spec(expression)
    codec = _codec_from_spec(spec)
    import svtypes

    return {
        "unified_type_name": svtypes.unified_type_name(codec),
        "python": spec["python"],
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
        {"unified_type_name", "python", "sv", "sv_packer", "encoding_descriptor"},
        where,
    )
    python = _object(raw.get("python"), f"{where}.python")
    _reject_unknown(python, {"module", "symbol", "args", "kwargs"}, f"{where}.python")
    args = python.get("args", [])
    kwargs = python.get("kwargs", {})
    if not isinstance(args, list):
        raise _error(f"{where}.python.args", "must be a JSON list")
    if not isinstance(kwargs, dict) or any(not isinstance(key, str) for key in kwargs):
        raise _error(f"{where}.python.kwargs", "must be a JSON object with string keys")
    descriptor = _object(raw.get("encoding_descriptor"), f"{where}.encoding_descriptor")
    _reject_unknown(
        descriptor,
        {"unified_type_name", "encoding_fingerprint", "binary_format_version"},
        f"{where}.encoding_descriptor",
    )
    binding = TypeBinding(
        _required_string(raw, "unified_type_name", where),
        _required_string(python, "module", f"{where}.python"),
        _identifier(
            _required_string(python, "symbol", f"{where}.python"),
            f"{where}.python.symbol",
        ),
        tuple(args),
        tuple(sorted(kwargs.items())),
        _required_string(raw, "sv", where),
        _required_string(raw, "sv_packer", where),
        tuple(sorted(descriptor.items())),
    )
    for field, content, grammar in (
        ("unified_type_name", binding.unified_type_name, r"[^\s]+"),
        ("python.module", binding.python_module, r"[A-Za-z_][A-Za-z0-9_.]*"),
        ("sv", binding.sv, r"[$A-Za-z_][A-Za-z0-9_:$#() ,]*"),
        ("sv_packer", binding.sv_packer, r"[A-Za-z_][A-Za-z0-9_:.$#() ,]*"),
    ):
        if not re.fullmatch(grammar, content):
            raise _error(f"{where}.{field}", "contains unsupported source characters")
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


def _parse_parameter(value: Any, where: str) -> Parameter:
    raw = _object(value, where)
    _reject_unknown(raw, {"name", "type", "direction", "ref_access"}, where)
    name = _identifier(_required_string(raw, "name", where), f"{where}.name")
    type_binding = _type_binding(raw.get("type"), f"{where}.type", allow_void=False)
    direction = raw.get("direction", "input")
    if direction not in {"input", "output", "inout", "ref"}:
        raise _error(f"{where}.direction", "must be input, output, inout, or ref")
    ref_access = raw.get("ref_access", "readwrite")
    if ref_access not in {"readwrite", "readonly"}:
        raise _error(f"{where}.ref_access", "must be readwrite or readonly")
    if direction != "ref" and "ref_access" in raw:
        raise _error(f"{where}.ref_access", "is valid only for ref parameters")
    assert type_binding is not None
    return Parameter(
        name=name,
        type_binding=type_binding,
        direction=direction,
        ref_access=ref_access,
    )


def _parse_field(value: Any, where: str) -> Field:
    raw = _object(value, where)
    _reject_unknown(raw, {"name", "type"}, where)
    name = _identifier(_required_string(raw, "name", where), f"{where}.name")
    type_binding = _type_binding(raw.get("type"), f"{where}.type", allow_void=False)
    assert type_binding is not None
    return Field(name, type_binding)


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
        return cls.name
    arguments: list[str] = []
    for argument in cls.specialization.arguments:
        if argument.kind == "type":
            assert argument.type_binding is not None
            arguments.append(argument.type_binding.sv)
        else:
            arguments.append(_sv_specialization_value(argument.value))
    return f"{cls.name}#({', '.join(arguments)})"


def _parse_method(value: Any, cls_id: str, where: str) -> Method:
    raw = _object(value, where)
    _reject_unknown(
        raw,
        {"canonical_id", "name", "parameters", "return_type", "timing", "virtual", "pure_virtual"},
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
    timing = _required_string(raw, "timing", where)
    if timing not in {"function", "task"}:
        raise _error(f"{where}.timing", "must be 'function' or 'task'")
    if timing == "task" and return_type is not None:
        raise _error(where, "task methods must have return_type 'void'")
    if return_type is not None and any(
        parameter.name == "result"
        and parameter.direction in {"output", "inout", "ref"}
        for parameter in parameters
    ):
        raise _error(
            f"{where}.parameters",
            "copy-out parameter name 'result' is reserved for the function return value",
        )

    virtual = raw.get("virtual")
    pure_virtual = raw.get("pure_virtual", False)
    if not isinstance(virtual, bool):
        raise _error(f"{where}.virtual", "must be a boolean")
    if not isinstance(pure_virtual, bool):
        raise _error(f"{where}.pure_virtual", "must be a boolean")
    if pure_virtual and not virtual:
        raise _error(where, "pure_virtual methods must also be virtual")
    return Method(canonical_id, name, parameters, return_type, timing, virtual, pure_virtual)


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


def parse_manifest(data: Any) -> Manifest:
    raw = _object(data, "root")
    _reject_unknown(
        raw,
        {
            "schema_uri",
            "schema_version",
            "generator_abi_version",
            "required_runtime_capabilities",
            "classes",
        },
        "root",
    )
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
        for ancestor in cls.base_lineage:
            declared = top_level.get(ancestor.canonical_id)
            if declared is not None and declared != ancestor:
                raise _error(
                    f"root.classes[{cls.canonical_id}].base_lineage",
                    f"description for {ancestor.canonical_id!r} differs from its top-level target",
                )
    return Manifest(
        schema_uri,
        schema_version,
        generator_abi_version,
        tuple(capabilities),
        classes,
    )


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
                    generated_name=f"{current.generated_name}Mirror",
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
                    generated_name=f"{current.generated_name}Proxy",
                    extends_class_id=current.canonical_id,
                )
            )
    return ProjectionPlan(target.canonical_id, tuple(lineage), tuple(steps))


def projection_plans(manifest: Manifest) -> tuple[ProjectionPlan, ...]:
    """Return deterministic, target-only plans for the complete manifest."""

    return tuple(projection_plan(target) for target in manifest.classes)


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
    for target in manifest.classes:
        for cls in (*target.base_lineage, target):
            previous = resolved.setdefault(cls.canonical_id, cls)
            if previous != cls:
                raise SVXInheritanceError(
                    f"conflicting lineage declarations for {cls.canonical_id}"
                )
    return tuple(resolved[key] for key in sorted(resolved))


def migrate_manifest(data: Any) -> dict[str, Any]:
    """Upgrade the executable v1 type syntax to the declarative v2 schema."""

    migrated = json.loads(json.dumps(data))
    for cls in migrated.get("classes", []):
        constructor = cls.get("constructor")
        groups = [constructor.get("parameters", [])] if isinstance(constructor, dict) else []
        for method in cls.get("methods", []):
            groups.append(method.get("parameters", []))
            method["return_type"] = _migrate_type_binding(
                method.get("return_type"), "method.return_type"
            )
        for parameters in groups:
            for parameter in parameters:
                parameter["type"] = _migrate_type_binding(
                    parameter.get("type"), "parameter.type"
                )
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
    return parse_manifest(data)


def _python_module_for(cls: ForeignClass) -> str:
    module = "svx_sv." + ".".join(cls.symbol.split("::")[:-1])
    # Preserve the foreign simple class name while isolating concrete
    # specializations in deterministic generated Python modules.
    if cls.specialization is not None:
        module += "__" + cls.generated_name.lower()
    return module


def _sv_package_for(cls: ForeignClass) -> str:
    return "svx_py_" + "_".join(cls.symbol.split(".")[:-1]) + "_pkg"


def _python_reverse_module_for(cls: ForeignClass) -> str:
    return "svx_py." + ".".join(cls.symbol.split(".")[:-1])


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
    return ", ".join(["self", *(parameter.name for parameter in method.parameters)])


def _python_request_parameter_list(method: Method) -> str:
    return ", ".join(
        ["self", *(parameter.name for parameter in _request_parameters(method))]
    )


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


def _response_field_specs(method: Method) -> str:
    fields = [
        (parameter.name, parameter.type_binding.runtime_spec())
        for parameter in _response_parameters(method)
    ]
    if method.return_type is not None:
        fields.append(("result", method.return_type.runtime_spec()))
    content = ", ".join(repr(field) for field in fields)
    return f"({content}{',' if len(fields) == 1 else ''})"


def _contract_repr(method: Method) -> str:
    return (
        "{'request': "
        + _field_specs(_request_parameters(method))
        + ", 'response': "
        + _response_field_specs(method)
        + "}"
    )


def _request_values_repr(method: Method) -> str:
    entries = ", ".join(
        f"{parameter.name!r}: {parameter.name}"
        for parameter in _request_parameters(method)
    )
    return "{" + entries + "}"


def _request_parameters(method: Method) -> tuple[Parameter, ...]:
    return tuple(
        parameter
        for parameter in method.parameters
        if parameter.direction in {"input", "inout", "ref"}
    )


def _response_parameters(method: Method) -> tuple[Parameter, ...]:
    return tuple(
        parameter
        for parameter in method.parameters
        if parameter.direction in {"output", "inout", "ref"}
    )


def emit_python_mirrors(manifest: Manifest) -> dict[PurePosixPath, str]:
    """Return relative output paths and declaration-only Python mirror source."""

    projected = _projected_class_ids(manifest)
    modules: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "sv" and cls.canonical_id not in projected:
            modules.setdefault(_python_module_for(cls), []).append(cls)

    emitted: dict[PurePosixPath, str] = {PurePosixPath("svx_sv/__init__.py"): "# Generated by svx inheritance-gen.\n"}
    for module_name, classes in sorted(modules.items()):
        module_parts = module_name.split(".")
        path = PurePosixPath(*module_parts).with_suffix(".py")
        lines = ["# Generated by svx inheritance-gen. Do not edit.", "from __future__ import annotations", "from svx import _native", "from svx.inheritance import bind_instance, encode_constructor, invoke_sv, register_constructor, register_contract, register_python_subclass, response_type, unbind_instance", ""]
        for cls in sorted(classes, key=lambda item: item.name):
            lines.append("register_contract({")
            for method in cls.methods:
                lines.append(
                    f"    {method.canonical_id!r}: {_contract_repr(method)},"
                )
            lines.append("})")
            if cls.constructor is not None:
                lines.append(
                    f"register_constructor({cls.canonical_id!r}, {_field_specs(cls.constructor.parameters)})"
                )
            if cls.constructor is not None and cls.constructor.initiator == "sv":
                lines.append("")
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init_subclass__(cls, **kwargs):", "        super().__init_subclass__(**kwargs)", f"        register_python_subclass({cls.canonical_id!r}, cls)", "", "    @classmethod", "    def __svx_create_from_sv__(cls, remote_object_id: int, *args):", "        instance = cls.__new__(cls)", "        instance._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, instance)", "        try:", "            cls.__init__(instance, *args)", "        except BaseException:", "            unbind_instance(remote_object_id)", "            raise", "        return instance", "", "    def __init__(self, *args):", "        if not hasattr(self, '_svx_remote_object_id'):", "            raise TypeError('SV-initiated inheritance instances must be created by SV')"])
            elif cls.constructor is not None and cls.constructor.initiator == "python":
                names = ", ".join(parameter.name for parameter in cls.constructor.parameters)
                signature = f"self, {names}" if names else "self"
                constructor_values = "{" + ", ".join(
                    f"{parameter.name!r}: {parameter.name}"
                    for parameter in cls.constructor.parameters
                ) + "}"
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init_subclass__(cls, **kwargs):", "        super().__init_subclass__(**kwargs)", f"        register_python_subclass({cls.canonical_id!r}, cls)", "", f"    def __init__({signature}):", f"        self._svx_remote_object_id = _native.inheritance_create_sv({cls.canonical_id!r}, encode_constructor({cls.canonical_id!r}, {constructor_values}))", "        try:", "            bind_instance(self._svx_remote_object_id, self)", "        except BaseException:", "            _native.inheritance_close(self._svx_remote_object_id)", "            raise"])
            else:
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init__(self, remote_object_id: int):", "        self._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, self)"])
            if not cls.methods:
                lines.append("    pass")
            for method in cls.methods:
                lines.extend(
                    [
                        "",
                        f"    def {method.name}({_python_request_parameter_list(method)}):",
                        f"        return invoke_sv(self._svx_remote_object_id, {method.canonical_id!r}, {_request_values_repr(method)})",
                    ]
                )
            lines.append("")
            for method in cls.methods:
                if _response_parameters(method):
                    response_name = f"{cls.name}{method.name[0].upper()}{method.name[1:]}Response"
                    lines.append(f"{response_name} = response_type({method.canonical_id!r})")
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"

    # Python counterparts of SV AMirror portions.  They are emitted only for
    # actual SV->Python boundaries and become the natural Python base imported
    # by user classes; no legacy foreign-name proxy is involved.
    projection_modules: dict[str, list[ForeignClass]] = {}
    for plan in projection_plans(manifest):
        for step in plan.steps:
            if step.kind != "sv_mirror":
                continue
            source = next(
                cls for cls in plan.lineage if cls.canonical_id == step.source_class_id
            )
            module = "svx_mirrors." + "_".join(source.symbol.split("::")[:-1])
            projection_modules.setdefault(module, []).append(source)
    if projection_modules:
        emitted[PurePosixPath("svx_mirrors/__init__.py")] = "# Generated by svx inheritance-gen.\n"
    for module, sources in sorted(projection_modules.items()):
        path = PurePosixPath(*module.split(".")).with_suffix(".py")
        lines = [
            "# Generated by svx inheritance-gen. Do not edit.",
            "from __future__ import annotations",
            "from svx import _native",
            "from svx.declarations import SVMirror",
            "from svx.inheritance import bind_instance, encode_constructor, invoke_sv, register_constructor, register_contract, register_python_subclass",
            "",
        ]
        seen: set[str] = set()
        for source in sorted(sources, key=lambda item: item.canonical_id):
            if source.canonical_id in seen:
                continue
            seen.add(source.canonical_id)
            lines.append("register_contract({")
            for method in source.methods:
                lines.append(f"    {method.canonical_id!r}: {_contract_repr(method)},")
            lines.append("})")
            parameters = source.constructor.parameters if source.constructor else ()
            if source.constructor is not None:
                lines.append(f"register_constructor({source.canonical_id!r}, {_field_specs(parameters)})")
            names = ", ".join(parameter.name for parameter in parameters)
            signature = f"self, {names}" if names else "self"
            values = "{" + ", ".join(f"{p.name!r}: {p.name}" for p in parameters) + "}"
            mirror_name = f"{source.generated_name}Mirror"
            lines.extend(
                [
                    "",
                    f"class {mirror_name}(SVMirror):",
                    f"    \"\"\"Executable Python base view of {source.symbol}.\"\"\"",
                    f"    __svx_foreign_class_id__ = {source.canonical_id!r}",
                    "",
                    "    def __init_subclass__(cls, **kwargs):",
                    "        super().__init_subclass__(**kwargs)",
                    f"        register_python_subclass({source.canonical_id!r}, cls)",
                    "",
                    "    @classmethod",
                    "    def __svx_create_from_sv__(cls, remote_object_id, *args):",
                    "        instance = cls.__new__(cls)",
                    "        SVMirror.__init__(instance)",
                    "        instance._svx_bind_remote_object(remote_object_id)",
                    "        bind_instance(remote_object_id, instance)",
                    "        try:",
                    "            cls.__init__(instance, *args)",
                    "        except BaseException:",
                    "            from svx.inheritance import unbind_instance",
                    "            unbind_instance(remote_object_id)",
                    "            raise",
                    "        return instance",
                    "",
                    f"    def __init__({signature}):",
                    "        if self._svx_remote_object_id is not None:",
                    "            return",
                    "        super().__init__()",
                    f"        object_id = _native.inheritance_create_sv({source.canonical_id!r}, encode_constructor({source.canonical_id!r}, {values}))",
                    "        self._svx_bind_remote_object(object_id)",
                    "        try:",
                    "            bind_instance(object_id, self)",
                    "        except BaseException:",
                    "            _native.inheritance_close(object_id)",
                    "            raise",
                ]
            )
            for method in source.methods:
                lines.extend(
                    [
                        "",
                        f"    def {method.name}({_python_request_parameter_list(method)}):",
                        f"        return invoke_sv(self._svx_remote_object_id, {method.canonical_id!r}, {_request_values_repr(method)})",
                    ]
                )
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"

    reverse_modules: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "python" and cls.canonical_id not in projected:
            reverse_modules.setdefault(_python_reverse_module_for(cls), []).append(cls)
    emitted[PurePosixPath("svx_py/__init__.py")] = "# Generated by svx inheritance-gen.\n"
    for module_name, classes in sorted(reverse_modules.items()):
        path = PurePosixPath(*module_name.split(".")).with_suffix(".py")
        lines = ["# Generated by svx inheritance-gen. Do not edit.", "from __future__ import annotations", "from svx import _native", "from svx.inheritance import bind_instance, encode_constructor, invoke_sv, register_constructor, register_contract, response_type", ""]
        for cls in sorted(classes, key=lambda item: item.name):
            source_module = ".".join(cls.symbol.split(".")[:-1])
            lines.extend([f"from {source_module} import {cls.name} as _Foreign{cls.name}", ""])
            lines.append("register_contract({")
            for method in cls.methods:
                lines.append(
                    f"    {method.canonical_id!r}: {_contract_repr(method)},"
                )
            lines.append("})")
            if cls.constructor is not None:
                lines.append(
                    f"register_constructor({cls.canonical_id!r}, {_field_specs(cls.constructor.parameters)})"
                )
            if (
                cls.constructor is not None
                and cls.constructor.initiator == "python"
            ):
                names = ", ".join(parameter.name for parameter in cls.constructor.parameters)
                signature = f"self, {names}" if names else "self"
                constructor_values = "{" + ", ".join(
                    f"{parameter.name!r}: {parameter.name}"
                    for parameter in cls.constructor.parameters
                ) + "}"
                lines.extend([f"class {cls.name}(_Foreign{cls.name}):", f"    \"\"\"Python view of an SV-derived {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", f"    def __init__({signature}):", f"        _Foreign{cls.name}.__init__(self{', ' if names else ''}{names})", f"        self._svx_remote_object_id = _native.inheritance_create_sv({cls.canonical_id!r}, encode_constructor({cls.canonical_id!r}, {constructor_values}))", "        try:", "            bind_instance(self._svx_remote_object_id, self)", "        except BaseException:", "            _native.inheritance_close(self._svx_remote_object_id)", "            raise", "", "    def __svx_dispatch_foreign__(self, method_name: str, *args):", f"        return getattr(_Foreign{cls.name}, method_name)(self, *args)"])
            else:
                lines.extend([f"class {cls.name}(_Foreign{cls.name}):", f"    \"\"\"Python view of an SV-derived {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init__(self, remote_object_id: int):", "        self._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, self)", "", "    def __svx_dispatch_foreign__(self, method_name: str, *args):", f"        return getattr(_Foreign{cls.name}, method_name)(self, *args)"])
            for method in cls.methods:
                lines.extend(["", f"    def {method.name}({_python_request_parameter_list(method)}):", f"        return invoke_sv(self._svx_remote_object_id, {method.canonical_id!r}, {_request_values_repr(method)})"])
            lines.append("")
            for method in cls.methods:
                if _response_parameters(method):
                    response_name = f"{cls.name}{method.name[0].upper()}{method.name[1:]}Response"
                    lines.append(f"{response_name} = response_type({method.canonical_id!r})")
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"
    return emitted


def _sv_parameters(method: Method) -> str:
    if not method.parameters:
        return ""
    def render(parameter: Parameter) -> str:
        direction = parameter.direction
        if direction == "ref" and parameter.ref_access == "readonly":
            direction = "const ref"
        return f"{direction} {parameter.type_binding.sv} {parameter.name}"

    return ", ".join(render(parameter) for parameter in method.parameters)


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
    schema = schema_type(
        _call_record_type_id(owner_id, kind),
        tuple((name, _codec_from_spec(binding.runtime_spec())) for name, binding in fields),
        class_name=_call_record_class_name(owner_id, kind),
    )
    value_type = schema.build()
    if value_type is None or not callable(getattr(value_type, "to_sv_obj", None)):
        raise SVXInheritanceError(
            f"SvTypes cannot generate the {kind} record for {owner_id}"
        )
    return value_type


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
                response += (("result", method.return_type),)
            if request:
                records.append(_sv_record_type(method.canonical_id, "request", request))
            if response:
                records.append(_sv_record_type(method.canonical_id, "response", response))
    return records


def _emit_sv_outbound_method(method: Method) -> list[str]:
    parameters = _sv_parameters(method)
    request_parameters = _request_parameters(method)
    response_parameters = _response_parameters(method)
    response_fields = bool(response_parameters or method.return_type is not None)
    result: list[str]
    if method.timing == "task":
        result = ["", f"    virtual task {method.name}({parameters});"]
    else:
        assert method.return_type is not None
        result = [
            "",
            f"    virtual function {method.return_type.sv} {method.name}({parameters});",
        ]
    result.extend(
        [
            "      bit ok;",
            "      chandle request;",
            "      chandle response;",
            "      string error;",
            "      byte unsigned bytes[$];",
        ]
    )
    if response_parameters or method.return_type is not None:
        result.append("      int offset;")
    if request_parameters:
        result.append(
            f"      {_call_record_class_name(method.canonical_id, 'request')} request_value;"
        )
    if response_fields:
        result.append(
            f"      {_call_record_class_name(method.canonical_id, 'response')} response_value;"
        )
    if method.return_type is not None:
        result.append(f"      {method.return_type.sv} result;")
    if request_parameters:
        result.append("      request_value = new();")
        for parameter in request_parameters:
            result.append(f"      request_value.{parameter.name} = {parameter.name};")
        result.append("      request_value.pack(bytes);")
    result.append(
        '      request = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");'
    )
    if method.timing == "task":
        result.append(
            f"      svx_inheritance_call_python(__svx_remote_object_id, {json.dumps(method.canonical_id)}, request, ok, response, error);"
        )
    else:
        result.append(
            f"      response = svx_inheritance_call_python_function(__svx_remote_object_id, {json.dumps(method.canonical_id)}, request, ok, error);"
        )
    result.extend(
        [
            "      svx_payload_destroy(request);",
            "      if (!ok) begin",
            f'        $fatal(2, "SVX inheritance callback {method.canonical_id} failed: %s", error);',
            "      end",
        ]
    )
    if response_parameters or method.return_type is not None:
        result.extend(
            [
                "      if (response == null) begin",
                f'        $fatal(2, "SVX inheritance callback {method.canonical_id} returned no response");',
                "      end",
                "      svx_payload_to_byte_queue(response, bytes);",
                "      svx_payload_destroy(response);",
                "      offset = 0;",
                "      response_value = new();",
                "      response_value.unpack(bytes, offset);",
            ]
        )
        for parameter in response_parameters:
            result.append(f"      {parameter.name} = response_value.{parameter.name};")
        if method.return_type is not None:
            result.append("      result = response_value.result;")
        result.append(
            f'      svx_require_unpacked_all("{method.canonical_id}", "inheritance response", "call response", offset, bytes.size());'
        )
    else:
        result.extend(
            [
                "      if (response != null) begin",
                "        svx_payload_destroy(response);",
                "      end",
            ]
        )
    if method.return_type is not None:
        result.append("      return result;")
        result.append("    endfunction")
    else:
        result.append("    endtask")
    return result


def _emit_sv_dispatch_case(method: Method, receiver: str = "") -> list[str]:
    result = [f"        {json.dumps(method.canonical_id)}: begin"]
    request_parameters = _request_parameters(method)
    response_parameters = _response_parameters(method)
    if request_parameters:
        result.append(
            f"          {_call_record_class_name(method.canonical_id, 'request')} request_value;"
        )
    if response_parameters or method.return_type is not None:
        result.append(
            f"          {_call_record_class_name(method.canonical_id, 'response')} response_value;"
        )
    for parameter in method.parameters:
        result.append(f"          {parameter.type_binding.sv} {parameter.name};")
    if method.return_type is not None:
        result.append(f"          {method.return_type.sv} result;")
    if request_parameters:
        result.extend(
            [
                "          request_value = new();",
                "          request_value.unpack(bytes, offset);",
            ]
        )
        for parameter in request_parameters:
            result.append(f"          {parameter.name} = request_value.{parameter.name};")
    result.append(
        f'          svx_require_unpacked_all("{method.canonical_id}", "inheritance request", "call request", offset, bytes.size());'
    )
    arguments = ", ".join(parameter.name for parameter in method.parameters)
    if method.return_type is None:
        result.append(f"          {receiver}{method.name}({arguments});")
    else:
        result.append(f"          result = {receiver}{method.name}({arguments});")
    result.append("          bytes.delete();")
    if response_parameters or method.return_type is not None:
        result.append("          response_value = new();")
        for parameter in response_parameters:
            result.append(f"          response_value.{parameter.name} = {parameter.name};")
        if method.return_type is not None:
            result.append("          response_value.result = result;")
        result.append("          response_value.pack(bytes);")
    result.extend(
        [
            "          ok = 1;",
            '          error = "";',
            '          response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
            "        end",
        ]
    )
    return result


def _emit_sv_field_dispatch_cases(cls: ForeignClass, field: Field) -> list[str]:
    """Emit root read/set endpoints used only by ``SVXFieldStorage``.

    SvTypes owns byte normalization and descriptor checking on the Python side;
    generated SV code owns the matching concrete packer and rejects trailing
    bytes. Path-aware collection endpoints are added with their explicit
    manifest operation table rather than silently doing whole-field writeback.
    """

    field_id = f"{cls.canonical_id}.{field.name}"
    packer = field.type_binding.sv_packer
    return [
        f"        {json.dumps(field_id + '@svx_field_read')}: begin",
        "          if (bytes.size() != 0) begin",
        "            ok = 0;",
        '            error = "field read request must be empty";',
        "          end else begin",
        "            bytes.delete();",
        f"            {packer}::pack({field.name}, bytes);",
        "            ok = 1;",
        '            error = "";',
        '            response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
        "          end",
        "        end",
        f"        {json.dumps(field_id + '@svx_field_set')}: begin",
        "          int field_offset;",
        "          field_offset = 0;",
        f"          {packer}::unpack({field.name}, bytes, field_offset);",
        f'          svx_require_unpacked_all("{field_id}", "field write", "field value", field_offset, bytes.size());',
        "          bytes.delete();",
        "          ok = 1;",
        '          error = "";',
        '          response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
        "        end",
    ]


def _emit_sv_projection_invoke(
    cls: ForeignClass,
    *,
    base_methods: tuple[Method, ...],
    delegate_unmatched_to_super: bool = False,
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
    for field in cls.fields:
        lines.extend(_emit_sv_field_dispatch_cases(cls, field))
    if delegate_unmatched_to_super:
        # A Python-to-SV proxy sits above an SV mirror.  Its inherited member
        # calls must reach the mirror's explicit base gateway, rather than
        # invoking the mirror's virtual override and re-entering Python.
        lines.extend(
            [
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
    return lines


def _emit_sv_projection_class(
    generated_name: str,
    base_type: str,
    cls: ForeignClass,
    *,
    base_methods: tuple[Method, ...],
    dispatch_virtuals: tuple[Method, ...],
    delegate_unmatched_to_super: bool = False,
) -> list[str]:
    """Emit an AMirror or BProxy portion without manufacturing user classes."""

    lines = [
        "",
        f"  class {generated_name} extends {base_type} implements svx_dispatchable;",
        "    longint unsigned __svx_remote_object_id;",
    ]
    for field in cls.fields:
        lines.append(f"    {field.type_binding.sv} {field.name};")
    constructor = cls.constructor
    constructor_parameters = (
        ", ".join(f"input {p.type_binding.sv} {p.name}" for p in constructor.parameters)
        if constructor is not None
        else ""
    )
    constructor_arguments = (
        ", ".join(p.name for p in constructor.parameters) if constructor is not None else ""
    )
    if constructor is not None and constructor.initiator == "sv":
        lines.extend(
            [
                "",
                f"    function new({constructor_parameters});",
                "      bit ok;",
                "      chandle request;",
                "      string error;",
                "      byte unsigned bytes[$];",
                *(
                    [
                        f"      {_call_record_class_name(cls.canonical_id, 'request')} request_value;"
                    ]
                    if constructor.parameters
                    else []
                ),
                f"      super.new({constructor_arguments});",
                "      __svx_remote_object_id = svx_inheritance_registry::allocate_object_id();",
            ]
        )
        if constructor.parameters:
            record_name = _call_record_class_name(cls.canonical_id, "request")
            lines.append("      request_value = new();")
            for parameter in constructor.parameters:
                lines.append(f"      request_value.{parameter.name} = {parameter.name};")
            lines.append("      request_value.pack(bytes);")
        lines.extend(
            [
                '      request = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
                f"      svx_inheritance_create_python({json.dumps(cls.canonical_id)}, __svx_remote_object_id, request, ok, error);",
                "      svx_payload_destroy(request);",
                "      if (!ok) begin",
                f'        $fatal(2, "SVX AMirror construction {cls.canonical_id} failed: %s", error);',
                "      end",
                "      svx_inheritance_registry::register_object(__svx_remote_object_id, this);",
                "    endfunction",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"    function new(longint unsigned object_id{', ' if constructor_parameters else ''}{constructor_parameters});",
                f"      super.new({constructor_arguments});",
                "      __svx_remote_object_id = object_id;",
                "      svx_inheritance_registry::register_object(object_id, this);",
                "    endfunction",
            ]
        )
    for method in dispatch_virtuals:
        lines.extend(_emit_sv_outbound_method(method))
    lines.extend(
        _emit_sv_projection_invoke(
            cls,
            base_methods=base_methods,
            delegate_unmatched_to_super=delegate_unmatched_to_super,
        )
    )
    lines.append(f"  endclass : {generated_name}")
    return lines


def _emit_sv_projection_factory(source: ForeignClass, helper_name: str) -> list[str]:
    """Factory used when Python creates the paired SV mirror/proxy object."""

    constructor = source.constructor
    if constructor is not None and constructor.initiator != "python":
        return []
    parameters = constructor.parameters if constructor is not None else ()
    record_name = _call_record_class_name(source.canonical_id, "request")
    factory_name = f"{helper_name}_factory"
    registration_name = f"register_{helper_name}_factory"
    lines = ["", f"  class {factory_name} implements svx_factory;", "    virtual task svx_create(longint unsigned object_id, input chandle request, output bit ok, output string error);"]
    if parameters:
        lines.extend(
            [
                f"      {record_name} constructor_request;",
                f"      {helper_name} instance;",
                f"      constructor_request = {record_name}::svx_decode_constructor_request(request);",
            ]
        )
        # Record classes use a static decoder on the generated mirror class in
        # the legacy path. Keep decoding local here so projection factories do
        # not require a second generated base class.
        lines[-1] = "      byte unsigned bytes[$];"
        lines.extend(
            [
                "      int offset;",
                "      constructor_request = new();",
                "      svx_payload_to_byte_queue(request, bytes);",
                "      offset = 0;",
                "      constructor_request.unpack(bytes, offset);",
                f'      svx_require_unpacked_all("{source.canonical_id}", "constructor request", "call request", offset, bytes.size());',
                f"      instance = new(object_id, {', '.join('constructor_request.' + p.name for p in parameters)});",
            ]
        )
    else:
        lines.extend([f"      {helper_name} instance;", "      instance = new(object_id);"])
    lines.extend(
        [
            "      ok = 1;",
            '      error = "";',
            "    endtask",
            f"  endclass : {factory_name}",
            "",
            f"  function void {registration_name}();",
            f"    static {factory_name} factory;",
            "    if (factory == null) factory = new();",
            f"    svx_inheritance_registry::register_factory({json.dumps(source.canonical_id)}, factory);",
            "  endfunction",
        ]
    )
    return lines


def _emit_sv_projection_helpers(
    manifest: Manifest,
    *,
    has_call_records: bool,
) -> list[str]:
    """Materialize only mirrors/proxies implied by top-level target lineages."""

    mirrors: dict[str, tuple[ForeignClass, ForeignClass]] = {}
    proxies: dict[str, tuple[ForeignClass, ForeignClass, ForeignClass]] = {}
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

    packages: dict[str, list[str]] = {}
    dependencies: dict[str, set[str]] = {}
    for source, _child in mirrors.values():
        package = "svx_projection_" + "_".join(source.symbol.split("::")[:-1]) + "_pkg"
        packages.setdefault(package, []).append(source.canonical_id)
    for source, _mirror, _child in proxies.values():
        package = "svx_projection_" + "_".join(source.symbol.split(".")[:-1]) + "_pkg"
        packages.setdefault(package, []).append(source.canonical_id)
        mirror_package = (
            "svx_projection_" + "_".join(_mirror.symbol.split("::")[:-1]) + "_pkg"
        )
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
                f"`ifndef {guard}",
                f"`define {guard}",
                "",
                f"package {package};",
                "  import svx_pkg::*;",
                "  import svtypes_pkg::*;",
                *(["  import svx_call_records_pkg::*;"] if has_call_records else []),
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
                mirror_package = "svx_projection_" + "_".join(mirror_source.symbol.split("::")[:-1]) + "_pkg"
                if mirror_package != package:
                    lines.append(f"  import {mirror_package}::*;")
        for class_id in class_ids:
            if class_id in mirrors:
                source, _child = mirrors[class_id]
                lines.extend(
                    _emit_sv_projection_class(
                        f"{source.generated_name}Mirror",
                        _sv_class_reference(source),
                        source,
                        base_methods=source.methods,
                        dispatch_virtuals=tuple(method for method in source.methods if method.virtual),
                    )
                )
                lines.extend(_emit_sv_projection_factory(source, f"{source.generated_name}Mirror"))
            if class_id in proxies:
                source, mirror_source, _child = proxies[class_id]
                lines.extend(
                    _emit_sv_projection_class(
                        f"{source.generated_name}Proxy",
                        f"{mirror_source.generated_name}Mirror",
                        source,
                        base_methods=mirror_source.methods,
                        dispatch_virtuals=tuple(method for method in source.methods if method.virtual),
                        delegate_unmatched_to_super=True,
                    )
                )
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])
    return lines


def emit_sv_mirrors(manifest: Manifest) -> str:
    """Emit target-scoped SV AMirror and Proxy projection helpers."""

    projected = _projected_class_ids(manifest)
    packages: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "python" and cls.canonical_id not in projected:
            packages.setdefault(
                "svx_projection_" + "_".join(cls.symbol.split(".")[:-1]) + "_pkg",
                [],
            ).append(cls)

    lines = ["// Generated by svx inheritance-gen. Do not edit."]
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
                "package svx_call_records_pkg;",
                "  import svtypes_pkg::*;",
                *(f"  import {package}::*;" for package in imported_packages),
            ]
        )
        for record_type in record_types:
            lines.extend(["", record_type.to_sv_obj(1)])
        lines.extend(["endpackage : svx_call_records_pkg", ""])
    record_import = ["  import svx_call_records_pkg::*;"] if record_types else []
    for package, classes in sorted(packages.items()):
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        lines.extend(["", f"`ifndef {guard}", f"`define {guard}", "", f"package {package};", "  import svx_pkg::*;", "  import svtypes_pkg::*;", *record_import])
        for cls in sorted(classes, key=lambda item: item.name):
            proxy_name = f"{cls.generated_name}Proxy"
            lines.extend(["", f"  // Generated SV projection for {cls.canonical_id}", f"  virtual class {proxy_name} implements svx_dispatchable;", "    longint unsigned __svx_remote_object_id;"])
            for field in cls.fields:
                lines.append(f"    {field.type_binding.sv} {field.name};")
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
                lines.extend(_emit_sv_outbound_method(method))
            lines.extend(["", "    virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);", "      byte unsigned bytes[$];", "      int offset;", "      response = null;", "      svx_payload_to_byte_queue(request, bytes);", "      offset = 0;", "      case (method_id)"])
            for method in cls.methods:
                lines.extend(_emit_sv_dispatch_case(method))
            for field in cls.fields:
                lines.extend(_emit_sv_field_dispatch_cases(cls, field))
            lines.extend(["        default: begin", "          ok = 0;", "          error = {\"unsupported method: \", method_id};", "        end", "      endcase", "    endtask"])
            lines.append(f"  endclass : {proxy_name}")
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])

    lines.extend(_emit_sv_projection_helpers(manifest, has_call_records=bool(record_types)))
    return "\n".join(lines).rstrip() + "\n"


def artifact_manifest(
    manifest: Manifest,
    python_sources: dict[PurePosixPath, str],
    sv_source: str,
    *,
    python_path_prefix: str = "",
    sv_path: str = "mirrors.sv",
) -> dict[str, Any]:
    """Describe generated inheritance artifacts for startup compatibility checks."""

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
    artifacts.append(
        {
            "language": "systemverilog",
            "path": sv_path,
            "sha256": hashlib.sha256(sv_source.encode("utf-8")).hexdigest(),
        }
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
    for cls in manifest.classes:
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
                            (("result", method.return_type),)
                            if method.return_type is not None
                            else ()
                        ),
                    ),
                    "request_fields": [
                        {
                            "name": parameter.name,
                            "direction": parameter.direction,
                            "ref_access": parameter.ref_access,
                            "unified_type_name": parameter.type_binding.unified_type_name,
                        }
                        for parameter in _request_parameters(method)
                    ],
                    "response_fields": [
                        {
                            "name": parameter.name,
                            "direction": parameter.direction,
                            "ref_access": parameter.ref_access,
                            "unified_type_name": parameter.type_binding.unified_type_name,
                        }
                        for parameter in _response_parameters(method)
                    ]
                    + (
                        [
                            {
                                "name": "result",
                                "direction": "return",
                                "unified_type_name": method.return_type.unified_type_name,
                            }
                        ]
                        if method.return_type is not None
                        else []
                    ),
                }
            )
    return {
        "schema_uri": "https://svx.dev/schema/generated-artifacts/v1",
        "schema_version": "1.0.0",
        "generator_abi_version": GENERATOR_ABI_VERSION,
        "svx_runtime_abi_version": 1,
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


def write_python_mirrors(manifest: Manifest, output_dir: Path) -> list[Path]:
    written: list[Path] = []
    for relative_path, text in emit_python_mirrors(manifest).items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, text)
        written.append(path)
    return written


def write_text_atomic(path: Path, text: str) -> None:
    """Atomically replace one generated UTF-8 text artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def bind_instance(object_id: int, instance: object) -> None:
    """Bind a Python object for an explicitly generated SV inheritance proxy."""

    if object_id <= 0 or object_id >= (1 << 64):
        raise ValueError("SVX inheritance object id must be an unsigned non-zero 64-bit value")
    from . import _native

    _native.inheritance_bind(object_id, instance)


def unbind_instance(object_id: int) -> None:
    """Release a binding previously created with :func:`bind_instance`."""

    from . import _native

    _native.inheritance_unbind(object_id)


def close_instance(object_id: int) -> None:
    """Release the paired Python and SystemVerilog inheritance bindings."""

    from . import _native

    _native.inheritance_close(object_id)


def call_sv(object_id: int, method_id: str, request: bytes = b"") -> bytes:
    """Call a manifest-generated SV adapter from an active SVX context."""

    if not isinstance(method_id, str) or not method_id:
        raise ValueError("SVX inheritance method_id must be a non-empty string")
    if not isinstance(request, bytes):
        raise TypeError("SVX inheritance request must be bytes")
    from . import _native

    try:
        return _native.inheritance_call_sv(object_id, method_id, request)
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


@dataclass
class _CallContract:
    request_fields: tuple[tuple[str, dict[str, Any]], ...]
    response_fields: tuple[tuple[str, dict[str, Any]], ...]
    request_schema: Any | None = None
    response_schema: Any | None = None


@dataclass(frozen=True)
class _RecordSchemaAdapter:
    schema: Any
    value_type: type

    def pack(self, value: Any, context: Any = None) -> bytes:
        return value.pack(value, context)

    def unpack(self, payload: bytes, context: Any = None):
        kwargs = {"_defer_identity": True}
        if context is not None:
            kwargs["session"] = context.session
        prototype = self.value_type(**kwargs)
        return prototype.unpack(payload, context)


_method_contracts: dict[str, _CallContract] = {}
_constructor_contracts: dict[str, _CallContract] = {}
_python_subclasses: dict[str, type] = {}


def _shutdown_python_state() -> None:
    """Clear generated contracts and factories at the simulator boundary."""

    _method_contracts.clear()
    _constructor_contracts.clear()
    _python_subclasses.clear()


def register_contract(
    contract: dict[str, dict[str, tuple[tuple[str, dict[str, Any]], ...]]]
) -> None:
    """Register generated method signatures used by the Python dispatch adapter.

    Each type is a declarative public SvTypes reference plus its immutable wire
    descriptor. No source expression is evaluated.
    """

    for method_id, signature in contract.items():
        if not isinstance(signature, dict) or set(signature) != {"request", "response"}:
            raise SVXInheritanceError(
                f"generated call contract {method_id} must contain request and response"
            )
        normalized = _CallContract(
            _normalize_call_fields(method_id, "request", signature["request"]),
            _normalize_call_fields(method_id, "response", signature["response"]),
        )
        existing = _method_contracts.get(method_id)
        if existing is not None and existing != normalized:
            raise SVXInheritanceError(f"conflicting SvTypes contract for {method_id}")
        _method_contracts[method_id] = normalized


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
) -> None:
    normalized = _CallContract(
        _normalize_call_fields(class_id, "constructor", fields), ()
    )
    existing = _constructor_contracts.get(class_id)
    if existing is not None and existing != normalized:
        raise SVXInheritanceError(f"conflicting SvTypes constructor contract for {class_id}")
    _constructor_contracts[class_id] = normalized


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
    for name, spec in fields:
        _validate_remote_refs(_svtypes_codec(spec), values[name])
    try:
        return schema.value_type(**values)
    except (AttributeError, TypeError):
        from .runtime import codec_session

        try:
            result = schema.value_type(session=codec_session())
            for name, _ in fields:
                member = getattr(result, name)
                if hasattr(member, "value"):
                    member.value = values[name]
                else:
                    setattr(result, name, values[name])
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


def response_type(method_id: str) -> type:
    """Return the generated SvTypes response value type for a method."""

    contract = _method_contracts.get(method_id)
    if not isinstance(contract, _CallContract):
        raise SVXInheritanceError(
            f"no generated response record contract registered for {method_id}"
        )
    schema = _contract_schema(contract, method_id, "response")
    if schema is None:
        raise SVXInheritanceError(f"method {method_id} has a void response")
    return schema.value_type


def invoke_sv(object_id: int, method_id: str, values: dict[str, Any]):
    """Invoke an SV method using its generated SvTypes request/response records."""

    contract = _method_contracts.get(method_id)
    if not isinstance(contract, _CallContract):
        raise SVXInheritanceError(
            f"no generated call-record contract registered for {method_id}"
        )
    request_schema = _contract_schema(contract, method_id, "request")
    if request_schema is None:
        if values:
            raise TypeError(f"method {method_id} has a void request")
        request = b""
    else:
        request = _pack_call_record(
            request_schema,
            _record_value(request_schema, contract.request_fields, values),
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
    if len(contract.response_fields) == 1 and contract.response_fields[0][0] == "result":
        return _record_field(response, "result")
    return response


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


def dispatch_python_call(object_id: int, method_id: str, payload: bytes) -> bytes:
    """C++ callback entry point; decode, invoke, and encode only through SvTypes."""

    contract = _method_contracts.get(method_id)
    if contract is None:
        raise SVXInheritanceError(f"no generated SvTypes contract registered for {method_id}")
    from . import _native

    instance = _native.inheritance_get(object_id)
    if instance is None:
        raise SVXInheritanceError(f"unknown Python inheritance object id {object_id}")
    method_name = method_id.rsplit("#", 1)[1]
    request_schema = _contract_schema(contract, method_id, "request")
    if request_schema is None:
        if payload:
            raise SVXInheritanceError(
                f"void inheritance request {method_id} contains data"
            )
        arguments = ()
    else:
        request = _unpack_call_record(request_schema, payload)
        _validate_record_fields(request, contract.request_fields)
        arguments = tuple(
            _record_field(request, name) for name, _ in contract.request_fields
        )
    foreign_dispatch = getattr(instance, "__svx_dispatch_foreign__", None)
    result = foreign_dispatch(method_name, *arguments) if foreign_dispatch else getattr(instance, method_name)(*arguments)
    response_schema = _contract_schema(contract, method_id, "response")
    if response_schema is None:
        if result is not None:
            raise SVXInheritanceError(
                f"void inheritance method {method_id} returned a value"
            )
        return b""
    if len(contract.response_fields) == 1 and contract.response_fields[0][0] == "result":
        response = _record_value(
            response_schema,
            contract.response_fields,
            {"result": result},
        )
    elif isinstance(result, response_schema.value_type):
        response = result
    else:
        raise SVXInheritanceError(
            f"inheritance method {method_id} must return "
            f"{response_schema.value_type.__name__} for copy-out values"
        )
    return _pack_call_record(response_schema, response)


def create_python_instance(class_id: str, object_id: int, payload: bytes) -> None:
    """DPI factory entry point for an SV-initiated generated pair."""

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
            _record_field(request, name) for name, _ in contract.request_fields
        )
    creator = getattr(subclass, "__svx_create_from_sv__", None)
    if creator is None:
        raise SVXInheritanceError(f"generated Python subclass factory is missing for {class_id}")
    creator(object_id, *arguments)
