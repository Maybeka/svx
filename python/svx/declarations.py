"""Declaration front ends that normalize cross-language classes to a manifest."""

from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Callable, Iterable

from .errors import SVXInheritanceError
from .inheritance import (
    EXTERNAL_FIELD_STORAGE_CAPABILITY,
    GENERATOR_ABI_VERSION,
    REQUIRED_RUNTIME_CAPABILITIES,
    SCHEMA_URI,
    SCHEMA_VERSION,
    Manifest,
    parse_manifest,
)
from .sv_scan import validate_sv_declarations

import svtypes
from svtypes import SvObject


SV_DECLARATION_SCHEMA_URI = "https://svx.dev/schema/sv-inheritance-declarations/v1"
SV_DECLARATION_SCHEMA_VERSION = "1.0.0"


def _declared_svtypes_fields(cls: type) -> list[dict[str, Any]]:
    """Render only fields declared directly by one Python inheritance class.

    SvTypes descriptors are instances rather than annotations.  Preserve the
    exact concrete descriptor through a private module-level zero-argument
    factory so the manifest remains data-only while nested types do not need
    to be expressed as executable JSON constructor arguments.
    """

    try:
        from svtypes.base import TypeBase
        from svtypes.object import ObjectDescriptor
    except ImportError as error:  # pragma: no cover - package prerequisite
        raise SVXInheritanceError("SvTypes is required to discover inheritance fields") from error

    direct = [
        (name, descriptor)
        for name, descriptor in cls.__dict__.items()
        if isinstance(descriptor, (TypeBase, ObjectDescriptor))
    ]
    if not direct:
        return []
    module = sys.modules.get(cls.__module__)
    if module is None:
        raise SVXInheritanceError(f"cannot locate module for inheritance class {cls.__name__}")
    fields: list[dict[str, Any]] = []
    for name, descriptor in direct:
        factory_name = f"__svx_declared_codec_{cls.__name__}_{name}"
        existing = getattr(module, factory_name, None)
        if existing is None:
            # Bind the descriptor as a default rather than closing over the
            # loop variable. Each resolution must receive a fresh codec.
            def factory(template=descriptor):
                return copy.deepcopy(template)

            factory.__name__ = factory_name
            factory.__qualname__ = factory_name
            setattr(module, factory_name, factory)
        elif not callable(existing):
            raise SVXInheritanceError(
                f"inheritance codec factory name {cls.__module__}.{factory_name} is unavailable"
            )
        try:
            fields.append(
                {
                    "name": name,
                    "type": {
                        "unified_type_name": svtypes.unified_type_name(descriptor),
                        "python": {
                            "module": cls.__module__,
                            "symbol": factory_name,
                            "args": [],
                            "kwargs": {},
                        },
                        "sv": svtypes.sv_type_expression(descriptor),
                        "sv_packer": svtypes.sv_packer_expression(descriptor),
                        "encoding_descriptor": svtypes.encoding_descriptor(descriptor).to_dict(),
                    },
                }
            )
        except Exception as error:
            raise SVXInheritanceError(
                f"cannot render SvTypes field {cls.__name__}.{name}: {error}"
            ) from error
    return fields


class SVMirror(SvObject):
    """Executable Python base for a declared SystemVerilog mirror surface.

    Generated mirror implementations extend this source declaration. The base
    intentionally owns no foreign object by itself: construction/binding is a
    generated lifecycle operation, not a side effect of importing a stub.
    """

    _svx_remote_object_id: int | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def _svx_bind_remote_object(self, object_id: int) -> None:
        if not isinstance(object_id, int) or object_id <= 0:
            raise ValueError("SVX mirror object id must be a non-zero integer")
        if self._svx_remote_object_id is not None:
            raise SVXInheritanceError("SVX mirror is already bound")
        self._svx_remote_object_id = object_id

    def _svx_bind_projected_fields(self, field_ids_by_name: dict[str, str]) -> None:
        """Bind selected SvTypes fields to this mirror's SV object storage.

        Generated lifecycle code invokes this only after the paired SV object
        exists. Fields absent from ``field_ids_by_name`` deliberately retain
        normal Python-local storage, which is what a direct Python child of an
        SV class requires.
        """

        if self._svx_remote_object_id is None:
            raise SVXInheritanceError("cannot bind projected fields before the SV mirror exists")
        from .field_storage import bind_projected_fields, projected_field_identities

        identities = projected_field_identities(self, field_ids_by_name)
        self._svx_field_storage = bind_projected_fields(
            self,
            self._svx_remote_object_id,
            identities,
        )

    def _svx_release_projected_fields(self) -> None:
        """Detach external fields before the paired SV object is released."""

        storage = getattr(self, "_svx_field_storage", None)
        self.unbind_external_storage()
        if storage is not None:
            storage.close()
            self._svx_field_storage = None


def sv_mirror(canonical_id: str):
    """Mark an ``SVMirror`` source class as the static view of one SV class.

    The decorator does not generate code or allocate an SV instance. During
    manifest discovery its canonical ID is matched to an explicit SV class
    declaration, from which the full ancestor context is obtained.
    """

    if not isinstance(canonical_id, str) or not canonical_id.startswith("sv://"):
        raise ValueError("sv_mirror canonical_id must be an sv:// identifier")

    def decorate(cls: type):
        if not isinstance(cls, type) or not issubclass(cls, SVMirror):
            raise TypeError("sv_mirror() requires an SVMirror subclass")
        if "__svx_sv_mirror__" in cls.__dict__:
            raise SVXInheritanceError(f"SV mirror {cls.__name__} is already declared")
        setattr(cls, "__svx_sv_mirror__", {"canonical_id": canonical_id})
        return cls

    return decorate


def inheritance_type(
    factory: Callable[..., Any],
    *args: Any,
    sv: str,
    sv_packer: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build one declarative manifest type reference from a public SvTypes factory."""

    if not callable(factory) or not isinstance(getattr(factory, "__module__", None), str):
        raise TypeError("inheritance_type() factory must be a public callable")
    symbol = getattr(factory, "__name__", None)
    if not isinstance(symbol, str) or not symbol.isidentifier():
        raise TypeError("inheritance_type() factory must have a public identifier name")
    try:
        json.dumps([args, kwargs])
    except (TypeError, ValueError) as error:
        raise TypeError("inheritance_type() arguments must be JSON values") from error
    codec = factory(*args, **kwargs)
    import svtypes

    descriptor = svtypes.encoding_descriptor(codec)
    return {
        "unified_type_name": svtypes.unified_type_name(codec),
        "python": {
            "module": factory.__module__,
            "symbol": symbol,
            "args": list(args),
            "kwargs": kwargs,
        },
        "sv": sv,
        "sv_packer": sv_packer,
        "encoding_descriptor": descriptor.to_dict(),
    }


def inheritance_parameter(
    name: str,
    type_binding: dict[str, Any],
    *,
    direction: str = "input",
) -> dict[str, Any]:
    """Declare one ordered inheritance parameter."""

    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("inheritance parameter name must be an identifier")
    if direction in {"ref", "const ref"}:
        raise ValueError("SVX inheritance does not support ref or const ref parameters; use input, output, or inout")
    if direction not in {"input", "output", "inout"}:
        raise ValueError("inheritance parameter direction is invalid")
    if not isinstance(type_binding, dict):
        raise TypeError("inheritance parameter type must be a declarative type binding")
    declaration = {"name": name, "type": type_binding, "direction": direction}
    return declaration


def inheritance_method(
    *,
    parameters: Iterable[dict[str, Any]] = (),
    return_type: dict[str, Any] | str = "void",
    timing: str = "task",
    virtual: bool = True,
    pure_virtual: bool = False,
):
    """Attach manifest method metadata to a Python-owned method."""

    declaration = {
        "parameters": list(parameters),
        "return_type": return_type,
        "timing": timing,
        "virtual": virtual,
        "pure_virtual": pure_virtual,
    }

    def decorate(function: Callable[..., Any]):
        if hasattr(function, "__svx_inheritance_method__"):
            raise SVXInheritanceError(
                f"inheritance method {function.__qualname__} is already declared"
            )
        setattr(function, "__svx_inheritance_method__", declaration)
        return function

    return decorate


def inheritance_class(
    *,
    canonical_id: str | None = None,
    constructor_parameters: Iterable[dict[str, Any]] = (),
    constructor_initiator: str = "python",
    base_lineage: Iterable[dict[str, Any]] | None = None,
    specialization: dict[str, Any] | None = None,
):
    """Declare one explicit Python generation target for manifest generation."""

    constructor = {
        "initiator": constructor_initiator,
        "parameters": list(constructor_parameters),
    }
    normalized_lineage = list(base_lineage or ())

    def decorate(cls: type):
        if not isinstance(cls, type):
            raise TypeError("inheritance_class() may only decorate a class")
        if "<locals>" in cls.__qualname__ or "." in cls.__qualname__:
            raise SVXInheritanceError("nested Python inheritance classes are unsupported")
        class_id = canonical_id or f"py://{cls.__module__.replace('.', '/')}/{cls.__name__}"
        mirror_bases = [
            base.__dict__["__svx_sv_mirror__"]["canonical_id"]
            for base in cls.__mro__[1:]
            if isinstance(base, type) and "__svx_sv_mirror__" in base.__dict__
        ]
        if len(mirror_bases) > 1:
            raise SVXInheritanceError(
                f"Python inheritance class {cls.__name__} has multiple SV mirror bases"
            )
        methods: list[dict[str, Any]] = []
        for name, member in cls.__dict__.items():
            metadata = getattr(member, "__svx_inheritance_method__", None)
            if metadata is None:
                continue
            request_names = [
                parameter["name"]
                for parameter in metadata["parameters"]
                if parameter.get("direction", "input") in {"input", "inout"}
            ]
            actual_names = list(inspect.signature(member).parameters)
            if actual_names != ["self", *request_names]:
                raise SVXInheritanceError(
                    f"Python inheritance method {cls.__name__}.{name} signature must be "
                    f"(self, {', '.join(request_names)})"
                )
            methods.append(
                {
                    "canonical_id": f"{class_id}#{name}",
                    "name": name,
                    **metadata,
                }
            )
        setattr(
            cls,
            "__svx_inheritance_class__",
            {
                "canonical_id": class_id,
                "language": "python",
                "symbol": f"{cls.__module__}.{cls.__name__}",
                "constructor": constructor,
                "methods": methods,
                "fields": _declared_svtypes_fields(cls),
                "base_lineage": normalized_lineage,
                "mirror_base_ids": mirror_bases,
                **({"specialization": specialization} if specialization is not None else {}),
            },
        )
        return cls

    return decorate


def _python_declarations(modules: Iterable[ModuleType]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for module in modules:
        for value in module.__dict__.values():
            declaration = (
                value.__dict__.get("__svx_inheritance_class__")
                if isinstance(value, type)
                else None
            )
            if isinstance(declaration, dict):
                if value.__module__ == module.__name__:
                    # Discovery may enrich a lineage; never mutate decorator
                    # metadata retained on the user's source class.
                    declarations.append(dict(declaration))
    return declarations


def load_sv_declarations(path: Path) -> list[dict[str, Any]]:
    """Load explicit, versioned SV declaration metadata from JSON."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SVXInheritanceError(f"cannot read SV declaration metadata {path}: {error}") from error
    if not isinstance(raw, dict) or set(raw) != {
        "schema_uri",
        "schema_version",
        "classes",
    }:
        raise SVXInheritanceError("SV declaration metadata root has invalid fields")
    if raw["schema_uri"] != SV_DECLARATION_SCHEMA_URI:
        raise SVXInheritanceError("unsupported SV declaration metadata schema")
    if raw["schema_version"] != SV_DECLARATION_SCHEMA_VERSION:
        raise SVXInheritanceError("unsupported SV declaration metadata version")
    classes = raw["classes"]
    if not isinstance(classes, list):
        raise SVXInheritanceError("SV declaration metadata classes must be a list")
    for declaration in classes:
        if not isinstance(declaration, dict) or declaration.get("language") != "sv":
            raise SVXInheritanceError("SV declaration metadata may contain only SV-owned classes")
    return classes


def manifest_from_declarations(
    *,
    python_modules: Iterable[ModuleType] = (),
    sv_declaration_files: Iterable[Path] = (),
    sv_source_files: Iterable[Path] = (),
) -> Manifest:
    """Normalize supported declaration front ends to the sole v2 manifest model."""

    classes = _python_declarations(python_modules)
    sv_classes: list[dict[str, Any]] = []
    for path in sv_declaration_files:
        sv_classes.extend(load_sv_declarations(path))
    if sv_source_files:
        validate_sv_declarations(sv_classes, sv_source_files)
    classes.extend(sv_classes)
    declared_by_id = {
        item.get("canonical_id"): item
        for item in classes
        if isinstance(item, dict) and isinstance(item.get("canonical_id"), str)
    }
    for declaration in classes:
        if declaration.get("language") != "python":
            continue
        mirror_base_ids = declaration.pop("mirror_base_ids", [])
        if declaration.get("base_lineage") or not mirror_base_ids:
            continue
        if len(mirror_base_ids) != 1:
            raise SVXInheritanceError("Python inheritance declaration has invalid mirror bases")
        base = declared_by_id.get(mirror_base_ids[0])
        if not isinstance(base, dict) or base.get("language") != "sv":
            raise SVXInheritanceError(
                f"Python mirror base {mirror_base_ids[0]!r} has no matching SV declaration"
            )
        # Manifest lineage is flat. Reuse the complete SV declaration context,
        # but never nest a lineage member inside another lineage member.
        inherited = base.get("base_lineage", [])
        if not isinstance(inherited, list):
            raise SVXInheritanceError("SV mirror base has invalid base_lineage")
        direct = {key: value for key, value in base.items() if key != "base_lineage"}
        declaration["base_lineage"] = [*inherited, direct]
    def declares_fields(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        if item.get("fields"):
            return True
        lineage = item.get("base_lineage", [])
        return isinstance(lineage, list) and any(declares_fields(base) for base in lineage)

    required_capabilities = list(REQUIRED_RUNTIME_CAPABILITIES)
    if any(declares_fields(item) for item in classes):
        required_capabilities.append(EXTERNAL_FIELD_STORAGE_CAPABILITY)
    return parse_manifest(
        {
            "schema_uri": SCHEMA_URI,
            "schema_version": SCHEMA_VERSION,
            "generator_abi_version": GENERATOR_ABI_VERSION,
            "required_runtime_capabilities": required_capabilities,
            "classes": classes,
        }
    )


def _class_declaration(cls: Any) -> dict[str, Any]:
    """Render a normalized class without recursively rendering its lineage."""

    declaration: dict[str, Any] = {
        "canonical_id": cls.canonical_id,
        "language": cls.language,
        "symbol": cls.symbol,
        "methods": [],
    }
    if cls.fields:
        declaration["fields"] = [
            {
                "name": field.name,
                "type": field.type_binding.runtime_spec()
                | {
                    "sv": field.type_binding.sv,
                    "sv_packer": field.type_binding.sv_packer,
                },
            }
            for field in cls.fields
        ]
    if cls.constructor is not None:
        declaration["constructor"] = {
            "initiator": cls.constructor.initiator,
            "parameters": [
                {
                    "name": parameter.name,
                    "type": parameter.type_binding.runtime_spec()
                    | {
                        "sv": parameter.type_binding.sv,
                        "sv_packer": parameter.type_binding.sv_packer,
                    },
                    "direction": parameter.direction,
                }
                for parameter in cls.constructor.parameters
            ],
        }
    for method in cls.methods:
        method_declaration = {
            "canonical_id": method.canonical_id,
            "name": method.name,
            "parameters": [
                {
                    "name": parameter.name,
                    "type": parameter.type_binding.runtime_spec()
                    | {
                        "sv": parameter.type_binding.sv,
                        "sv_packer": parameter.type_binding.sv_packer,
                    },
                    "direction": parameter.direction,
                }
                for parameter in method.parameters
            ],
            "return_type": (
                method.return_type.runtime_spec()
                | {
                    "sv": method.return_type.sv,
                    "sv_packer": method.return_type.sv_packer,
                }
                if method.return_type is not None
                else "void"
            ),
            "timing": method.timing,
            "virtual": method.virtual,
            "pure_virtual": method.pure_virtual,
        }
        if method.is_static:
            method_declaration["static"] = True
        declaration["methods"].append(method_declaration)
    if cls.specialization is not None:
        declaration["specialization"] = {
            "arguments": [
                (
                    {
                        "kind": "type",
                        "type": argument.type_binding.runtime_spec()
                        | {
                            "sv": argument.type_binding.sv,
                            "sv_packer": argument.type_binding.sv_packer,
                        },
                    }
                    if argument.kind == "type"
                    else {
                        "kind": "value",
                        "sv_type": argument.sv_type,
                        "value": argument.value,
                    }
                )
                for argument in cls.specialization.arguments
            ]
        }
    return declaration


def manifest_dict(manifest: Manifest) -> dict[str, Any]:
    """Return the validated JSON representation of a generated manifest."""

    classes: list[dict[str, Any]] = []
    for cls in manifest.classes:
        declaration = _class_declaration(cls)
        if cls.base_lineage:
            declaration["base_lineage"] = [
                _class_declaration(ancestor) for ancestor in cls.base_lineage
            ]
        classes.append(declaration)
    return {
        "schema_uri": manifest.schema_uri,
        "schema_version": manifest.schema_version,
        "generator_abi_version": manifest.generator_abi_version,
        "required_runtime_capabilities": list(manifest.required_runtime_capabilities),
        "classes": classes,
    }
