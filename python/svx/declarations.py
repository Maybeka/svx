"""Declaration front ends that normalize cross-language classes to a manifest."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

from .errors import SVXInheritanceError
from .inheritance import (
    GENERATOR_ABI_VERSION,
    REQUIRED_RUNTIME_CAPABILITIES,
    SCHEMA_URI,
    SCHEMA_VERSION,
    Manifest,
    parse_manifest,
)
from .sv_scan import validate_sv_declarations


SV_DECLARATION_SCHEMA_URI = "https://svx.dev/schema/sv-inheritance-declarations/v1"
SV_DECLARATION_SCHEMA_VERSION = "1.0.0"


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
    name: str, type_binding: dict[str, Any], *, direction: str = "input"
) -> dict[str, Any]:
    """Declare one ordered inheritance parameter."""

    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("inheritance parameter name must be an identifier")
    if direction not in {"input", "output", "inout", "ref"}:
        raise ValueError("inheritance parameter direction is invalid")
    if not isinstance(type_binding, dict):
        raise TypeError("inheritance parameter type must be a declarative type binding")
    return {"name": name, "type": type_binding, "direction": direction}


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
        methods: list[dict[str, Any]] = []
        for name, member in cls.__dict__.items():
            metadata = getattr(member, "__svx_inheritance_method__", None)
            if metadata is None:
                continue
            request_names = [
                parameter["name"]
                for parameter in metadata["parameters"]
                if parameter.get("direction", "input") in {"input", "inout", "ref"}
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
                "base_lineage": normalized_lineage,
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
                    declarations.append(declaration)
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
    return parse_manifest(
        {
            "schema_uri": SCHEMA_URI,
            "schema_version": SCHEMA_VERSION,
            "generator_abi_version": GENERATOR_ABI_VERSION,
            "required_runtime_capabilities": list(REQUIRED_RUNTIME_CAPABILITIES),
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
        declaration["methods"].append(
            {
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
        )
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
