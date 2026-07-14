"""Manifest, mirrors, and SvTypes-backed cross-language inheritance dispatch."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .errors import SVXInheritanceError, SVXRemoteError


SCHEMA_URI = "https://svx.dev/schema/inheritance-manifest/v1"
SCHEMA_VERSION = "1.0.0"
_LEGACY_TYPES = {
    "bit": {"svtypes": "svtypes.Bits(1)", "sv": "bit", "sv_packer": "bits_packer#(bit)"},
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
    """One SvTypes codec and its corresponding generated SV adapter."""

    svtypes: str
    sv: str
    sv_packer: str


@dataclass(frozen=True)
class Parameter:
    name: str
    type_binding: TypeBinding
    direction: str


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
class ForeignClass:
    canonical_id: str
    language: str
    symbol: str
    methods: tuple[Method, ...]
    constructor: Constructor | None

    @property
    def name(self) -> str:
        return self.symbol.split("::")[-1].split(".")[-1]


@dataclass(frozen=True)
class Manifest:
    schema_uri: str
    schema_version: str
    classes: tuple[ForeignClass, ...]


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


def _type_binding(value: Any, where: str, *, allow_void: bool) -> TypeBinding | None:
    if allow_void and value == "void":
        return None
    raw = _object(value, where)
    _reject_unknown(raw, {"svtypes", "sv", "sv_packer"}, where)
    binding = TypeBinding(
        _required_string(raw, "svtypes", where),
        _required_string(raw, "sv", where),
        _required_string(raw, "sv_packer", where),
    )
    for field, content, grammar in (
        ("svtypes", binding.svtypes, r"[A-Za-z_][A-Za-z0-9_.:$() ,]*"),
        ("sv", binding.sv, r"[$A-Za-z_][A-Za-z0-9_:$#() ,]*"),
        ("sv_packer", binding.sv_packer, r"[A-Za-z_][A-Za-z0-9_:.$#() ,]*"),
    ):
        if not re.fullmatch(grammar, content):
            raise _error(f"{where}.{field}", "contains unsupported source characters")
    return binding


def _parse_parameter(value: Any, where: str) -> Parameter:
    raw = _object(value, where)
    _reject_unknown(raw, {"name", "type", "direction"}, where)
    name = _identifier(_required_string(raw, "name", where), f"{where}.name")
    type_binding = _type_binding(raw.get("type"), f"{where}.type", allow_void=False)
    direction = raw.get("direction", "input")
    if direction != "input":
        raise _error(f"{where}.direction", "only 'input' is supported in M8")
    assert type_binding is not None
    return Parameter(name=name, type_binding=type_binding, direction=direction)


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


def _parse_class(value: Any, where: str) -> ForeignClass:
    raw = _object(value, where)
    _reject_unknown(raw, {"canonical_id", "language", "symbol", "methods", "constructor"}, where)
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

    raw_methods = raw.get("methods", [])
    if not isinstance(raw_methods, list):
        raise _error(f"{where}.methods", "must be a list")
    methods = tuple(_parse_method(item, canonical_id, f"{where}.methods[{index}]") for index, item in enumerate(raw_methods))
    method_names = [method.name for method in methods]
    if len(method_names) != len(set(method_names)):
        raise _error(f"{where}.methods", "method overloads are not supported; names must be unique")
    constructor_raw = raw.get("constructor")
    constructor = _parse_constructor(constructor_raw, f"{where}.constructor") if constructor_raw is not None else None
    return ForeignClass(canonical_id, language, symbol, methods, constructor)


def parse_manifest(data: Any) -> Manifest:
    raw = _object(data, "root")
    _reject_unknown(raw, {"schema_uri", "schema_version", "classes"}, "root")
    schema_uri = _required_string(raw, "schema_uri", "root")
    if schema_uri != SCHEMA_URI:
        raise _error("root.schema_uri", f"must be {SCHEMA_URI!r}")
    schema_version = _required_string(raw, "schema_version", "root")
    if not _SCHEMA_VERSION.fullmatch(schema_version) or schema_version.split(".", 1)[0] != "1":
        raise _error("root.schema_version", "must be a supported semver version with major version 1")
    raw_classes = raw.get("classes")
    if not isinstance(raw_classes, list) or not raw_classes:
        raise _error("root.classes", "must be a non-empty list")
    classes = tuple(_parse_class(item, f"root.classes[{index}]") for index, item in enumerate(raw_classes))
    class_ids = [cls.canonical_id for cls in classes]
    if len(class_ids) != len(set(class_ids)):
        raise _error("root.classes", "contains duplicate canonical class IDs")
    _validate_generated_names(classes)
    return Manifest(schema_uri, schema_version, classes)


def migrate_manifest(data: Any) -> dict[str, Any]:
    """Upgrade early v1 scalar spellings and validate the canonical result."""

    migrated = json.loads(json.dumps(data))
    for cls in migrated.get("classes", []):
        constructor = cls.get("constructor")
        groups = [constructor.get("parameters", [])] if isinstance(constructor, dict) else []
        for method in cls.get("methods", []):
            groups.append(method.get("parameters", []))
            result = method.get("return_type")
            if isinstance(result, str) and result in _LEGACY_TYPES:
                method["return_type"] = dict(_LEGACY_TYPES[result])
        for parameters in groups:
            for parameter in parameters:
                legacy = parameter.get("type")
                if isinstance(legacy, str) and legacy in _LEGACY_TYPES:
                    parameter["type"] = dict(_LEGACY_TYPES[legacy])
    migrated["schema_uri"] = SCHEMA_URI
    migrated["schema_version"] = SCHEMA_VERSION
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
    return "svx_sv." + ".".join(cls.symbol.split("::")[:-1])


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
        key = (target, namespace, cls.name)
        previous = seen.get(key)
        if previous is not None:
            raise _error(
                "root.classes",
                f"generated {target} name {namespace}.{cls.name} collides between "
                f"{previous.canonical_id!r} and {cls.canonical_id!r}",
            )
        seen[key] = cls


def _python_parameter_list(method: Method) -> str:
    return ", ".join(["self", *(parameter.name for parameter in method.parameters)])


def _type_expressions(method: Method) -> str:
    return ", ".join(repr(parameter.type_binding.svtypes) for parameter in method.parameters)


def emit_python_mirrors(manifest: Manifest) -> dict[PurePosixPath, str]:
    """Return relative output paths and declaration-only Python mirror source."""

    modules: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "sv":
            modules.setdefault(_python_module_for(cls), []).append(cls)

    emitted: dict[PurePosixPath, str] = {PurePosixPath("svx_sv/__init__.py"): "# Generated by svx inheritance-gen.\n"}
    for module_name, classes in sorted(modules.items()):
        module_parts = module_name.split(".")
        path = PurePosixPath(*module_parts).with_suffix(".py")
        lines = ["# Generated by svx inheritance-gen. Do not edit.", "from __future__ import annotations", "from svx.inheritance import bind_instance, call_sv, decode_result, encode_arguments, register_constructor, register_contract, register_python_subclass", ""]
        for cls in sorted(classes, key=lambda item: item.name):
            lines.append("register_contract({")
            for method in cls.methods:
                return_expr = repr(method.return_type.svtypes) if method.return_type else "None"
                lines.append(f"    {method.canonical_id!r}: (({_type_expressions(method)}{',' if len(method.parameters) == 1 else ''}), {return_expr}),")
            lines.append("})")
            if cls.constructor is not None and cls.constructor.initiator == "sv":
                constructor_types = ", ".join(repr(parameter.type_binding.svtypes) for parameter in cls.constructor.parameters)
                lines.extend([f"register_constructor({cls.canonical_id!r}, ({constructor_types}{',' if len(cls.constructor.parameters) == 1 else ''}))", ""])
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init_subclass__(cls, **kwargs):", "        super().__init_subclass__(**kwargs)", f"        register_python_subclass({cls.canonical_id!r}, cls)", "", "    @classmethod", "    def __svx_create_from_sv__(cls, remote_object_id: int, *args):", "        instance = cls.__new__(cls)", "        instance._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, instance)", "        cls.__init__(instance, *args)", "        return instance", "", "    def __init__(self, *args):", "        if not hasattr(self, '_svx_remote_object_id'):", "            raise TypeError('SV-initiated inheritance instances must be created by SV')"])
            else:
                lines.extend([f"class {cls.name}:", f"    \"\"\"Mirror for {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init__(self, remote_object_id: int):", "        self._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, self)"])
            if not cls.methods:
                lines.append("    pass")
            for method in cls.methods:
                lines.extend(
                    [
                        "",
                        f"    def {method.name}({_python_parameter_list(method)}):",
                        f"        return decode_result(call_sv(self._svx_remote_object_id, {method.canonical_id!r}, encode_arguments(({', '.join(parameter.name for parameter in method.parameters)}{',' if len(method.parameters) == 1 else ''}), ({_type_expressions(method)}{',' if len(method.parameters) == 1 else ''}))), {repr(method.return_type.svtypes) if method.return_type else 'None'})",
                    ]
                )
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"

    reverse_modules: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "python":
            reverse_modules.setdefault(_python_reverse_module_for(cls), []).append(cls)
    emitted[PurePosixPath("svx_py/__init__.py")] = "# Generated by svx inheritance-gen.\n"
    for module_name, classes in sorted(reverse_modules.items()):
        path = PurePosixPath(*module_name.split(".")).with_suffix(".py")
        lines = ["# Generated by svx inheritance-gen. Do not edit.", "from __future__ import annotations", "from svx import _native", "from svx.inheritance import bind_instance, call_sv, decode_result, encode_arguments, register_contract", ""]
        for cls in sorted(classes, key=lambda item: item.name):
            source_module = ".".join(cls.symbol.split(".")[:-1])
            lines.extend([f"from {source_module} import {cls.name} as _Foreign{cls.name}", ""])
            lines.append("register_contract({")
            for method in cls.methods:
                return_expr = repr(method.return_type.svtypes) if method.return_type else "None"
                lines.append(f"    {method.canonical_id!r}: (({_type_expressions(method)}{',' if len(method.parameters) == 1 else ''}), {return_expr}),")
            lines.append("})")
            if cls.constructor is not None and cls.constructor.initiator == "python":
                names = ", ".join(parameter.name for parameter in cls.constructor.parameters)
                types = ", ".join(repr(parameter.type_binding.svtypes) for parameter in cls.constructor.parameters)
                values_tuple = f"({names}{',' if len(cls.constructor.parameters) == 1 else ''})"
                types_tuple = f"({types}{',' if len(cls.constructor.parameters) == 1 else ''})"
                signature = f"self, {names}" if names else "self"
                lines.extend([f"class {cls.name}(_Foreign{cls.name}):", f"    \"\"\"Python view of an SV-derived {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", f"    def __init__({signature}):", f"        _Foreign{cls.name}.__init__(self{', ' if names else ''}{names})", f"        self._svx_remote_object_id = _native.inheritance_create_sv({cls.canonical_id!r}, encode_arguments({values_tuple}, {types_tuple}))", "        bind_instance(self._svx_remote_object_id, self)", "", "    def __svx_dispatch_foreign__(self, method_name: str, *args):", f"        return getattr(_Foreign{cls.name}, method_name)(self, *args)"])
            else:
                lines.extend([f"class {cls.name}(_Foreign{cls.name}):", f"    \"\"\"Python view of an SV-derived {cls.symbol}.\"\"\"", f"    __svx_foreign_class_id__ = {cls.canonical_id!r}", "", "    def __init__(self, remote_object_id: int):", "        self._svx_remote_object_id = remote_object_id", "        bind_instance(remote_object_id, self)", "", "    def __svx_dispatch_foreign__(self, method_name: str, *args):", f"        return getattr(_Foreign{cls.name}, method_name)(self, *args)"])
            for method in cls.methods:
                lines.extend(["", f"    def {method.name}({_python_parameter_list(method)}):", f"        return decode_result(call_sv(self._svx_remote_object_id, {method.canonical_id!r}, encode_arguments(({', '.join(parameter.name for parameter in method.parameters)}{',' if len(method.parameters) == 1 else ''}), ({_type_expressions(method)}{',' if len(method.parameters) == 1 else ''}))), {repr(method.return_type.svtypes) if method.return_type else 'None'})"])
            lines.append("")
        emitted[path] = "\n".join(lines).rstrip() + "\n"
    return emitted


def _sv_parameters(method: Method) -> str:
    if not method.parameters:
        return ""
    return ", ".join(f"input {parameter.type_binding.sv} {parameter.name}" for parameter in method.parameters)


def emit_sv_mirrors(manifest: Manifest) -> str:
    """Emit M8 mirrors and M9 zero-argument SV-to-Python proxy subclasses."""

    packages: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "python":
            packages.setdefault(_sv_package_for(cls), []).append(cls)

    lines = ["// Generated by svx inheritance-gen. Do not edit."]
    for package, classes in sorted(packages.items()):
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        lines.extend(["", f"`ifndef {guard}", f"`define {guard}", "", f"package {package};", "  import svx_pkg::*;", "  import svtypes_pkg::*;"])
        for cls in sorted(classes, key=lambda item: item.name):
            lines.extend(["", f"  // Generated SV base for {cls.canonical_id}", f"  virtual class {cls.name} implements svx_dispatchable;", "    longint unsigned __svx_remote_object_id;", "", "    function new(longint unsigned object_id);", "      __svx_remote_object_id = object_id;", "      svx_inheritance_registry::register_object(object_id, this);", "    endfunction"])
            for method in cls.methods:
                parameters = _sv_parameters(method)
                if method.timing == "task":
                    lines.extend(["", f"    virtual task {method.name}({parameters});", "      bit ok;", "      chandle request;", "      chandle response;", "      string error;", "      byte unsigned bytes[$];"])
                    for parameter in method.parameters:
                        lines.append(f"      {parameter.type_binding.sv_packer}::pack({parameter.name}, bytes);")
                    lines.extend(["      request = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", f"      svx_inheritance_call_python(__svx_remote_object_id, {json.dumps(method.canonical_id)}, request, ok, response, error);", "      svx_payload_destroy(request);", "      if (response != null) begin", "        svx_payload_destroy(response);", "      end", "      if (!ok) begin", f"        $fatal(2, \"SVX inheritance callback {method.canonical_id} failed: %s\", error);", "      end", "    endtask"])
                else:
                    assert method.return_type is not None
                    lines.extend(["", f"    virtual function {method.return_type.sv} {method.name}({parameters});", "      bit ok;", "      chandle request;", "      chandle response;", "      string error;", "      byte unsigned bytes[$];", "      int offset;", f"      {method.return_type.sv} result;"])
                    for parameter in method.parameters:
                        lines.append(f"      {parameter.type_binding.sv_packer}::pack({parameter.name}, bytes);")
                    lines.extend(["      request = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", f"      response = svx_inheritance_call_python_function(__svx_remote_object_id, {json.dumps(method.canonical_id)}, request, ok, error);", "      svx_payload_destroy(request);", "      if (!ok) begin", f"        $fatal(2, \"SVX inheritance function callback {method.canonical_id} failed: %s\", error);", "      end", "      svx_payload_to_byte_queue(response, bytes);", "      svx_payload_destroy(response);", "      offset = 0;", f"      {method.return_type.sv_packer}::unpack(result, bytes, offset);", "      return result;", "    endfunction"])
            lines.extend(["", "    virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);", "      byte unsigned bytes[$];", "      int offset;", "      response = null;", "      svx_payload_to_byte_queue(request, bytes);", "      offset = 0;", "      case (method_id)"])
            for method in cls.methods:
                lines.append(f"        {json.dumps(method.canonical_id)}: begin")
                for parameter in method.parameters:
                    lines.append(f"          {parameter.type_binding.sv} {parameter.name};")
                if method.return_type is not None:
                    lines.append(f"          {method.return_type.sv} result;")
                for parameter in method.parameters:
                    lines.append(f"          {parameter.type_binding.sv_packer}::unpack({parameter.name}, bytes, offset);")
                if method.return_type is None:
                    lines.extend([f"          {method.name}({', '.join(parameter.name for parameter in method.parameters)});", "          bytes.delete();"])
                else:
                    lines.extend([f"          result = {method.name}({', '.join(parameter.name for parameter in method.parameters)});", "          bytes.delete();", f"          {method.return_type.sv_packer}::pack(result, bytes);"])
                lines.extend(["          ok = 1;", "          error = \"\";", "          response = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", "        end"])
            lines.extend(["        default: begin", "          ok = 0;", "          error = {\"unsupported method: \", method_id};", "        end", "      endcase", "    endtask"])
            lines.append(f"  endclass : {cls.name}")
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])

    proxy_packages: dict[str, list[ForeignClass]] = {}
    for cls in manifest.classes:
        if cls.language == "sv":
            proxy_packages.setdefault("svx_pyproxy_" + "_".join(cls.symbol.split("::")[:-1]) + "_pkg", []).append(cls)
    for package, classes in sorted(proxy_packages.items()):
        guard = re.sub(r"[^A-Za-z0-9_]", "_", package.upper()) + "__SV"
        lines.extend(["", f"`ifndef {guard}", f"`define {guard}", "", f"package {package};", "  import svx_pkg::*;", "  import svtypes_pkg::*;"])
        for cls in sorted(classes, key=lambda item: item.name):
            base_package = cls.symbol.split("::")[0]
            lines.extend([f"  import {base_package}::*;", "", f"  class {cls.name}_python_proxy extends {cls.name} implements svx_dispatchable;", "    longint unsigned __svx_remote_object_id;"])
            if cls.constructor is not None and cls.constructor.initiator == "sv":
                constructor_parameters = ", ".join(
                    f"input {parameter.type_binding.sv} {parameter.name}"
                    for parameter in cls.constructor.parameters
                )
                super_arguments = ", ".join(parameter.name for parameter in cls.constructor.parameters)
                lines.extend(["", f"    function new({constructor_parameters});", "      bit ok;", "      chandle request;", "      string error;", "      byte unsigned bytes[$];", f"      super.new({super_arguments});", "      __svx_remote_object_id = svx_inheritance_registry::allocate_object_id();"])
                for parameter in cls.constructor.parameters:
                    lines.append(f"      {parameter.type_binding.sv_packer}::pack({parameter.name}, bytes);")
                lines.extend(["      request = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", f"      svx_inheritance_create_python({json.dumps(cls.canonical_id)}, __svx_remote_object_id, request, ok, error);", "      svx_payload_destroy(request);", "      if (!ok) begin", f"        $fatal(2, \"SVX inheritance factory {cls.canonical_id} failed: %s\", error);", "      end", "      svx_inheritance_registry::register_object(__svx_remote_object_id, this);", "    endfunction"])
            else:
                lines.extend(["", "    function new(longint unsigned object_id);", "      super.new();", "      __svx_remote_object_id = object_id;", "      svx_inheritance_registry::register_object(object_id, this);", "    endfunction"])
            for method in cls.methods:
                if method.timing != "task" or method.return_type is not None:
                    if method.timing != "function" or method.return_type is None:
                        continue
                    lines.extend(["", f"    virtual function {method.return_type.sv} {method.name}({_sv_parameters(method)});", "      bit ok;", "      chandle request;", "      chandle response;", "      string error;", "      byte unsigned bytes[$];", "      int offset;", f"      {method.return_type.sv} result;"])
                    for parameter in method.parameters:
                        lines.append(f"      {parameter.type_binding.sv_packer}::pack({parameter.name}, bytes);")
                    lines.extend(["      request = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", f"      response = svx_inheritance_call_python_function(__svx_remote_object_id, {json.dumps(method.canonical_id)}, request, ok, error);", "      svx_payload_destroy(request);", "      if (!ok) begin", f"        $fatal(2, \"SVX inheritance function callback {method.canonical_id} failed: %s\", error);", "      end", "      svx_payload_to_byte_queue(response, bytes);", "      svx_payload_destroy(response);", "      offset = 0;", f"      {method.return_type.sv_packer}::unpack(result, bytes, offset);", "      return result;", "    endfunction"])
                    continue
                lines.extend(["", f"    virtual task {method.name}({_sv_parameters(method)});", "      bit ok;", "      chandle request;", "      chandle response;", "      string error;", "      byte unsigned bytes[$];"])
                for parameter in method.parameters:
                    lines.append(f"      {parameter.type_binding.sv_packer}::pack({parameter.name}, bytes);")
                lines.extend(["      request = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", f"      svx_inheritance_call_python(__svx_remote_object_id, {json.dumps(method.canonical_id)}, request, ok, response, error);", "      svx_payload_destroy(request);", "      if (response != null) begin", "        svx_payload_destroy(response);", "      end", "      if (!ok) begin", f"        $fatal(2, \"SVX inheritance callback {method.canonical_id} failed: %s\", error);", "      end", "    endtask"])
            lines.extend(["", "    virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);", "      byte unsigned bytes[$];", "      int offset;", "      response = null;", "      svx_payload_to_byte_queue(request, bytes);", "      offset = 0;"])
            dispatch_methods = [
                method
                for method in cls.methods
                if (method.timing == "task" and method.return_type is None)
                or (method.timing == "function" and method.return_type is not None)
            ]
            if dispatch_methods:
                lines.append("      case (method_id)")
                for method in dispatch_methods:
                    lines.append(f"        {json.dumps(method.canonical_id)}: begin")
                    for parameter in method.parameters:
                        lines.append(f"          {parameter.type_binding.sv} {parameter.name};")
                    if method.return_type is not None:
                        lines.append(f"          {method.return_type.sv} result;")
                    for parameter in method.parameters:
                        lines.append(f"          {parameter.type_binding.sv_packer}::unpack({parameter.name}, bytes, offset);")
                    if method.return_type is None:
                        lines.extend([f"          super.{method.name}({', '.join(parameter.name for parameter in method.parameters)});", "          bytes.delete();"])
                    else:
                        lines.extend([f"          result = super.{method.name}({', '.join(parameter.name for parameter in method.parameters)});", "          bytes.delete();", f"          {method.return_type.sv_packer}::pack(result, bytes);"])
                    lines.extend(["          ok = 1;", "          error = \"\";", "          response = svx_payload_from_byte_queue(bytes, \"svx-inheritance\", \"\", \"application/x-svx-inheritance\");", "        end"])
                lines.extend(["        default: begin", "          ok = 0;", "          error = {\"unsupported base method: \", method_id};", "        end", "      endcase"])
            else:
                lines.extend(["      ok = 0;", "      error = {\"no supported base method for: \", method_id};"])
            lines.extend(["    endtask"])
            lines.extend([f"  endclass : {cls.name}_python_proxy"])
        lines.extend([f"endpackage : {package}", "", f"`endif // {guard}"])
    return "\n".join(lines).rstrip() + "\n"


def write_python_mirrors(manifest: Manifest, output_dir: Path) -> list[Path]:
    written: list[Path] = []
    for relative_path, text in emit_python_mirrors(manifest).items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(path)
    return written


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


_method_contracts: dict[str, tuple[tuple[str, ...], str | None]] = {}
_constructor_contracts: dict[str, tuple[str, ...]] = {}
_python_subclasses: dict[str, type] = {}


def register_contract(contract: dict[str, tuple[tuple[str, ...], str | None]]) -> None:
    """Register generated method signatures used by the Python dispatch adapter.

    The strings are SvTypes factory expressions. SVX never interprets their wire
    representation: it delegates every value to the resulting ``TypeBase``.
    """

    for method_id, signature in contract.items():
        if method_id in _method_contracts and _method_contracts[method_id] != signature:
            raise SVXInheritanceError(f"conflicting SvTypes contract for {method_id}")
        _method_contracts[method_id] = signature


def register_constructor(class_id: str, type_expressions: tuple[str, ...]) -> None:
    existing = _constructor_contracts.get(class_id)
    if existing is not None and existing != type_expressions:
        raise SVXInheritanceError(f"conflicting SvTypes constructor contract for {class_id}")
    _constructor_contracts[class_id] = type_expressions


def register_python_subclass(class_id: str, subclass: type) -> None:
    existing = _python_subclasses.get(class_id)
    if existing is not None and existing is not subclass:
        raise SVXInheritanceError(
            f"multiple Python subclasses registered for {class_id}: "
            f"{existing.__module__}.{existing.__name__} and {subclass.__module__}.{subclass.__name__}"
        )
    _python_subclasses[class_id] = subclass


def _svtypes_codec(expression: str):
    import importlib
    import svtypes

    namespace = {"svtypes": svtypes}
    codec_expression = expression
    if ":" in expression:
        module_name, codec_expression = expression.split(":", 1)
        module = importlib.import_module(module_name)
        namespace.update(vars(module))
    try:
        codec = eval(codec_expression, {"__builtins__": {}}, namespace)
    except Exception as error:
        raise SVXInheritanceError(f"cannot construct SvTypes codec {expression!r}: {error}") from error
    if not hasattr(codec, "pack") or not hasattr(codec, "unpack"):
        raise SVXInheritanceError(f"SvTypes codec {expression!r} does not implement pack/unpack")
    return codec


def encode_arguments(values: tuple[object, ...], type_expressions: tuple[str, ...]) -> bytes:
    """Concatenate declared SvTypes encodings in manifest parameter order."""

    if len(values) != len(type_expressions):
        raise TypeError(f"expected {len(type_expressions)} arguments, got {len(values)}")
    return b"".join(_svtypes_codec(expression).pack(value) for value, expression in zip(values, type_expressions))


def _decode_arguments(payload: bytes, type_expressions: tuple[str, ...]) -> tuple[object, ...]:
    values: list[object] = []
    offset = 0
    for expression in type_expressions:
        value, consumed = _svtypes_codec(expression).unpack(payload[offset:])
        if not isinstance(consumed, int) or consumed < 0:
            raise SVXInheritanceError(f"SvTypes codec {expression!r} returned invalid byte count")
        values.append(value)
        offset += consumed
    if offset != len(payload):
        raise SVXInheritanceError(f"SvTypes argument payload has {len(payload) - offset} trailing bytes")
    return tuple(values)


def decode_result(payload: bytes, type_expression: str | None):
    """Decode a declared result, or verify an empty SvTypes void response."""

    if type_expression is None:
        if payload:
            raise SVXInheritanceError("void inheritance method returned a non-empty SvTypes payload")
        return None
    value, consumed = _svtypes_codec(type_expression).unpack(payload)
    if consumed != len(payload):
        raise SVXInheritanceError("SvTypes result payload has trailing bytes")
    return value


def dispatch_python_call(object_id: int, method_id: str, payload: bytes) -> bytes:
    """C++ callback entry point; decode, invoke, and encode only through SvTypes."""

    contract = _method_contracts.get(method_id)
    if contract is None:
        raise SVXInheritanceError(f"no generated SvTypes contract registered for {method_id}")
    from . import _native

    instance = _native.inheritance_get(object_id)
    if instance is None:
        raise SVXInheritanceError(f"unknown Python inheritance object id {object_id}")
    parameters, return_type = contract
    method_name = method_id.rsplit("#", 1)[1]
    arguments = _decode_arguments(payload, parameters)
    foreign_dispatch = getattr(instance, "__svx_dispatch_foreign__", None)
    result = foreign_dispatch(method_name, *arguments) if foreign_dispatch else getattr(instance, method_name)(*arguments)
    if return_type is None:
        if result is not None:
            raise SVXInheritanceError(f"void inheritance method {method_id} returned a value")
        return b""
    return _svtypes_codec(return_type).pack(result)


def create_python_instance(class_id: str, object_id: int, payload: bytes) -> None:
    """DPI factory entry point for an SV-initiated generated pair."""

    type_expressions = _constructor_contracts.get(class_id)
    subclass = _python_subclasses.get(class_id)
    if type_expressions is None or subclass is None:
        raise SVXInheritanceError(f"no generated Python factory registered for {class_id}")
    arguments = _decode_arguments(payload, type_expressions)
    creator = getattr(subclass, "__svx_create_from_sv__", None)
    if creator is None:
        raise SVXInheritanceError(f"generated Python subclass factory is missing for {class_id}")
    creator(object_id, *arguments)
