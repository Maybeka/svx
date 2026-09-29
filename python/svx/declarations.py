"""Declaration front ends that normalize cross-language classes to a manifest."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import inspect
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Annotated, Any, Callable, Generic, Iterable, TypeAlias, TypeVar

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
from .sv_scan import SVVirtualInterfaceFact, scan_sv_virtual_interfaces, validate_sv_declarations

import svtypes
from svtypes import SvObject


SV_DECLARATION_SCHEMA_URI = "https://svx.dev/schema/sv-inheritance-declarations/v1"
SV_DECLARATION_SCHEMA_VERSION = "1.0.0"
_UNSET = object()


@dataclass(frozen=True)
class _ParameterMarker:
    direction: str
    type_declaration: Any


@dataclass(frozen=True)
class _FunctionMarker:
    return_type: Any


def _svtypes_binding(annotation: Any, *, where: str) -> dict[str, Any]:
    """Derive all manifest data from SvTypes' public boundary contract."""

    try:
        if not svtypes.is_materializable_type(annotation):
            raise TypeError("not a concrete SvTypes boundary type")
        codec = svtypes.materialize_type_spec(annotation, location=where)
        return {
            "unified_type_name": svtypes.unified_type_name(codec),
            "svtypes": svtypes.type_spec_identity(annotation, location=where),
            "sv": svtypes.sv_type_expression(codec),
            "sv_packer": svtypes.sv_packer_expression(codec),
            "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict(),
        }
    except Exception as error:
        raise TypeError(f"{where} must be a concrete SvTypes boundary type: {error}") from error


def _type_declaration(value: Any, *, where: str) -> dict[str, Any]:
    """Accept modern SvTypes annotations while retaining legacy manifests."""

    if isinstance(value, dict):
        return value
    return _svtypes_binding(value, where=where)


_T = TypeVar("_T")


if TYPE_CHECKING:
    # These aliases make declaration metadata transparent to Pyright.  Runtime
    # marker classes below preserve the same concise annotation syntax.
    Input: TypeAlias = _T
    Function: TypeAlias = Annotated[_T, "svx.Function"]
    Task: TypeAlias = Annotated[None, "svx.Task"]

    class Output(Generic[_T]):
        value: _T

        def __init__(self) -> None: ...

    class Inout(Generic[_T]):
        value: _T

        def __init__(self, value: _T) -> None: ...

else:
    class _ParameterDirection:
        _direction = ""

        def __init__(self, value: Any = _UNSET) -> None:
            self._svx_copyout_value = value

        @property
        def value(self) -> Any:
            if self._svx_copyout_value is _UNSET:
                raise SVXInheritanceError(
                    f"svx.{type(self).__name__} value is not available before the foreign call completes"
                )
            return self._svx_copyout_value

        @value.setter
        def value(self, value: Any) -> None:
            self._svx_copyout_value = value

        @property
        def _svx_copyout_is_set(self) -> bool:
            return self._svx_copyout_value is not _UNSET

        @classmethod
        def __class_getitem__(cls, type_declaration: Any) -> _ParameterMarker:
            return _ParameterMarker(cls._direction, type_declaration)


    class Input(_ParameterDirection):
        """Function-annotation marker for an ``input`` SvTypes parameter."""

        _direction = "input"


    class Output(_ParameterDirection):
        """Function-annotation marker for an ``output`` SvTypes parameter."""

        _direction = "output"


    class Inout(_ParameterDirection):
        """Function-annotation marker for an ``inout`` SvTypes parameter."""

        _direction = "inout"

        def __init__(self, value: Any = _UNSET) -> None:
            if value is _UNSET:
                raise TypeError("svx.Inout(value) requires an initial value")
            super().__init__(value)


    class Task:
        """Return annotation marking an inheritance member as an SV task."""

        @classmethod
        def __class_getitem__(cls, value: object):
            raise TypeError("svx.Task has no function return type; use -> svx.Task")


    class Function:
        """Return annotation marking an inheritance member as an SV function."""

        @classmethod
        def __class_getitem__(cls, return_type: Any) -> _FunctionMarker:
            return _FunctionMarker(return_type)


def _resolved_annotations(function: Callable[..., Any]) -> dict[str, Any]:
    """Resolve annotations while preserving a focused declaration diagnostic."""

    try:
        return inspect.get_annotations(function, eval_str=True)
    except (NameError, TypeError) as error:
        raise SVXInheritanceError(
            f"cannot resolve annotations for inheritance method {function.__qualname__}: {error}"
        ) from error


def _return_declaration(function: Callable[..., Any], annotations: dict[str, Any]) -> tuple[str | None, Any]:
    """Return the optional timing and SvTypes result binding from ``->``."""

    annotation = annotations.get("return", inspect.Signature.empty)
    if (
        annotation is inspect.Signature.empty
        or annotation is None
        or annotation is type(None)
    ):
        return None, _UNSET
    if annotation is Task:
        return "task", _UNSET
    if annotation is Function:
        return "function", _UNSET
    if isinstance(annotation, _FunctionMarker):
        return "function", _type_declaration(
            annotation.return_type,
            where=f"inheritance method {function.__qualname__} return annotation",
        )
    raise SVXInheritanceError(
        f"inheritance method {function.__qualname__} return annotation must be "
        "svx.Task, svx.Function, or svx.Function[SVTYPES_TYPE]"
    )


def _parameter_declarations_from_annotations(
    function: Callable[..., Any], annotations: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """Build parameters from ``T``, ``Input[T]``, ``Output[T]``, and ``Inout[T]``."""

    parameters = list(inspect.signature(function).parameters.values())
    if not parameters or parameters[0].name != "self":
        return None
    declared: list[dict[str, Any]] = []
    saw_marker = False
    for parameter in parameters[1:]:
        annotation = annotations.get(parameter.name, inspect.Signature.empty)
        if not isinstance(annotation, _ParameterMarker) and annotation is not inspect.Signature.empty:
            annotation = _ParameterMarker("input", annotation)
        if annotation is inspect.Signature.empty:
            if saw_marker:
                raise SVXInheritanceError(
                    f"inheritance method {function.__qualname__} must annotate every "
                    "non-self parameter with a binding, svx.Input, svx.Output, or svx.Inout"
                )
            continue
        if not isinstance(annotation, _ParameterMarker):
            raise SVXInheritanceError(
                f"inheritance method {function.__qualname__}.{parameter.name} annotation must be "
                "a SvTypes type, svx.Input[TYPE], svx.Output[TYPE], or svx.Inout[TYPE]"
            )
        if not saw_marker and declared:
            raise SVXInheritanceError(
                f"inheritance method {function.__qualname__} must annotate every "
                "non-self parameter with a binding, svx.Input, svx.Output, or svx.Inout"
            )
        saw_marker = True
        declared.append(
            inheritance_parameter(
                parameter.name,
                _type_declaration(
                    annotation.type_declaration,
                    where=f"inheritance method {function.__qualname__}.{parameter.name}",
                ),
                direction=annotation.direction,
            )
        )
    return declared if saw_marker else None


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


def inheritance_parameter(
    name: str,
    type_binding: Any,
    *,
    direction: str = "input",
    handle: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Declare one ordered inheritance parameter."""

    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("inheritance parameter name must be an identifier")
    if direction in {"ref", "const ref"}:
        raise ValueError("SVX inheritance does not support ref or const ref parameters; use input, output, or inout")
    if direction not in {"input", "output", "inout"}:
        raise ValueError("inheritance parameter direction is invalid")
    declaration = {
        "name": name,
        "type": _type_declaration(type_binding, where=f"inheritance parameter {name}"),
        "direction": direction,
    }
    if handle is not None:
        if not isinstance(handle, dict):
            raise TypeError("inheritance handle metadata must be a dictionary")
        declaration["handle"] = dict(handle)
    return declaration


def sv_class_handle(target_type_name: str, sv_type: str) -> dict[str, str]:
    """Declare the static SV class type behind a ``RemoteRef`` boundary value."""

    if not isinstance(target_type_name, str) or not target_type_name.startswith("sv://"):
        raise ValueError("SV class handle target must use an sv:// type name")
    if not isinstance(sv_type, str) or not sv_type.strip():
        raise ValueError("SV class handle requires a non-empty static SV type")
    return {
        "kind": "sv_class",
        "target_type_name": target_type_name,
        "sv_type": sv_type,
    }


def virtual_interface_handle(target_type_name: str, sv_type: str) -> dict[str, str]:
    """Declare the static virtual-interface type behind a ``RemoteRef`` value."""

    if not isinstance(target_type_name, str) or not target_type_name.startswith("sv-vif://"):
        raise ValueError("virtual-interface handle target must use an sv-vif:// type name")
    if not isinstance(sv_type, str) or not sv_type.startswith("virtual "):
        raise ValueError("virtual-interface handle requires a 'virtual <interface>[.<modport>]' type")
    return {
        "kind": "virtual_interface",
        "target_type_name": target_type_name,
        "sv_type": sv_type,
    }


def inheritance_method(
    function: Callable[..., Any] | None = None,
    *,
    parameters: Iterable[dict[str, Any]] | None = None,
    return_type: dict[str, Any] | str | object = _UNSET,
    timing: str | None = None,
    virtual: bool = True,
    pure_virtual: bool = False,
    return_handle: dict[str, str] | None = None,
):
    """Attach manifest metadata, optionally inferred from a Python prototype.

    The concise form is ``@inheritance_method`` with ``T``, ``Input[T]``,
    ``Output[T]``, or ``Inout[T]`` parameter annotations and a ``Task`` or ``Function[T]``
    return annotation. The explicit keyword form remains available.
    """

    def decorate(method: Callable[..., Any]):
        if hasattr(method, "__svx_inheritance_method__"):
            raise SVXInheritanceError(
                f"inheritance method {method.__qualname__} is already declared"
            )
        annotations = _resolved_annotations(method)
        annotation_parameters = _parameter_declarations_from_annotations(method, annotations)
        annotation_timing, annotation_return_type = _return_declaration(method, annotations)
        if parameters is not None and annotation_parameters is not None:
            raise SVXInheritanceError(
                f"inheritance method {method.__qualname__} cannot mix parameters= with "
                "prototype parameter annotations"
            )
        if return_type is not _UNSET and annotation_return_type is not _UNSET:
            raise SVXInheritanceError(
                f"inheritance method {method.__qualname__} cannot mix return_type= with "
                "svx.Function[TYPE]"
            )
        if timing is not None and timing not in {"function", "task"}:
            raise SVXInheritanceError(
                f"inheritance method {method.__qualname__} timing must be 'function' or 'task'"
            )
        if timing is not None and annotation_timing is not None and timing != annotation_timing:
            raise SVXInheritanceError(
                f"inheritance method {method.__qualname__} timing={timing!r} conflicts "
                f"with return annotation {annotation_timing!r}"
            )
        declaration = {
            "parameters": list(parameters) if parameters is not None else (annotation_parameters or []),
            "return_type": (
                _type_declaration(
                    return_type,
                    where=f"inheritance method {method.__qualname__} return_type",
                )
                if return_type is not _UNSET
                else annotation_return_type if annotation_return_type is not _UNSET else "void"
            ),
            "timing": annotation_timing or timing or "task",
            "virtual": virtual,
            "pure_virtual": pure_virtual,
        }
        if return_handle is not None:
            if not isinstance(return_handle, dict):
                raise TypeError("inheritance return handle metadata must be a dictionary")
            declaration["return_handle"] = dict(return_handle)
        setattr(method, "__svx_inheritance_method__", declaration)
        return method

    if function is None:
        return decorate
    if not callable(function):
        raise TypeError("inheritance_method() requires a callable")
    return decorate(function)


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
            signature_parameters = list(inspect.signature(member).parameters.values())
            actual_names = [parameter.name for parameter in signature_parameters]
            expected_names = ["self", *(
                parameter["name"] for parameter in metadata["parameters"]
            )]
            if actual_names != expected_names:
                raise SVXInheritanceError(
                    f"Python inheritance method {cls.__name__}.{name} signature must be "
                    f"(self, {', '.join(expected_names[1:])})"
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

    sv_source_files = tuple(sv_source_files)
    # Nested method/handle dictionaries are intentionally enriched below;
    # never mutate decorator metadata retained on the user's Python classes.
    classes = [copy.deepcopy(item) for item in _python_declarations(python_modules)]
    sv_classes: list[dict[str, Any]] = []
    for path in sv_declaration_files:
        sv_classes.extend(load_sv_declarations(path))
    if sv_source_files:
        validate_sv_declarations(sv_classes, sv_source_files)
    classes.extend(sv_classes)
    if sv_source_files:
        _enrich_virtual_interface_handles(classes, scan_sv_virtual_interfaces(sv_source_files))
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


def _vif_type_declaration(sv_type: str, *, where: str) -> dict[str, Any]:
    """Map the supported static SV scalar subset to a public SvTypes type."""

    normalized = " ".join(sv_type.split())
    match = re.fullmatch(r"(bit|logic)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?", normalized)
    if match:
        base, left, right = match.groups()
        width = 1 if left is None else abs(int(left) - int(right)) + 1
        annotation = (svtypes.Bit if base == "bit" else svtypes.Logic)[width]
        return _svtypes_binding(annotation, where=where)
    scalar_types = {
        "int": svtypes.Int,
        "integer": svtypes.Int,
        "longint": svtypes.LongInt,
        "string": svtypes.String,
        "real": svtypes.Real,
    }
    annotation = scalar_types.get(normalized)
    if annotation is None:
        raise SVXInheritanceError(
            f"{where} uses {sv_type!r}, which has no declared SvTypes VIF mapping"
        )
    return _svtypes_binding(annotation, where=where)


def _vif_operations(
    target_type_name: str,
    fact: SVVirtualInterfaceFact,
    modport: str | None,
) -> list[dict[str, Any]]:
    if modport is None:
        directions = {member.name: "inout" for member in fact.members}
    else:
        directions = {
            item.name: item.direction
            for name, items in fact.modport_members
            if name == modport
            for item in items
        }
    operations: list[dict[str, Any]] = []
    for member in fact.members:
        direction = directions.get(member.name)
        if direction is None:
            continue
        if member.kind == "signal":
            assert member.sv_type is not None
            binding = _vif_type_declaration(
                member.sv_type,
                where=f"virtual interface {fact.symbol}.{member.name}",
            )
            if direction in {"input", "inout"}:
                operations.append(
                    {
                        "operation": "signal_read",
                        "member": member.name,
                        "method": {
                            "canonical_id": f"{target_type_name}#read_{member.name}",
                            "name": f"read_{member.name}",
                            "parameters": [],
                            "return_type": binding,
                            "timing": "function",
                        },
                    }
                )
            if direction in {"output", "inout"}:
                operations.append(
                    {
                        "operation": "signal_write",
                        "member": member.name,
                        "method": {
                            "canonical_id": f"{target_type_name}#write_{member.name}",
                            "name": f"write_{member.name}",
                            "parameters": [{"name": "value", "type": binding, "direction": "input"}],
                            "return_type": "void",
                            "timing": "task",
                        },
                    }
                )
            continue
        # A full virtual-interface type has no modport visibility filter:
        # every declared subroutine is callable.  A modport, in contrast,
        # exposes only subroutines explicitly imported by that modport.
        if modport is not None and direction != "import":
            continue
        parameters = []
        for parameter in member.parameters:
            if parameter.direction not in {"input", "output", "inout"}:
                raise SVXInheritanceError(
                    f"virtual interface {fact.symbol}.{member.name}.{parameter.name} "
                    f"uses unsupported direction {parameter.direction!r}"
                )
            parameters.append(
                {
                    "name": parameter.name,
                    "type": _vif_type_declaration(
                        parameter.sv_type,
                        where=f"virtual interface {fact.symbol}.{member.name}.{parameter.name}",
                    ),
                    "direction": parameter.direction,
                }
            )
        return_type: Any = "void"
        if member.kind == "function":
            assert member.sv_type is not None
            return_type = _vif_type_declaration(
                member.sv_type,
                where=f"virtual interface {fact.symbol}.{member.name} return",
            )
        operations.append(
            {
                "operation": member.kind,
                "member": member.name,
                "method": {
                    "canonical_id": f"{target_type_name}#{member.name}",
                    "name": member.name,
                    "parameters": parameters,
                    "return_type": return_type,
                    "timing": member.kind,
                },
            }
        )
    return operations


def _enrich_virtual_interface_handles(
    classes: list[dict[str, Any]], facts: dict[str, SVVirtualInterfaceFact]
) -> None:
    """Attach generated VIF operations to handle metadata in-place."""

    def enrich_handle(handle: object) -> None:
        if not isinstance(handle, dict) or handle.get("kind") != "virtual_interface":
            return
        if handle.get("operations"):
            return
        sv_type = handle.get("sv_type")
        target = handle.get("target_type_name")
        if not isinstance(sv_type, str) or not isinstance(target, str):
            return
        match = re.fullmatch(r"virtual\s+([A-Za-z_$][A-Za-z0-9_$:]*)((?:\.[A-Za-z_$][A-Za-z0-9_$]*)?)", sv_type)
        if match is None:
            raise SVXInheritanceError(
                f"virtual interface handle type {sv_type!r} is not a supported static VIF declaration"
            )
        interface_name, modport_suffix = match.groups()
        modport = modport_suffix[1:] if modport_suffix else None
        fact = facts.get(interface_name)
        if fact is None:
            raise SVXInheritanceError(
                f"virtual interface {interface_name} was not found in scanned SV sources"
            )
        expected_target = f"sv-vif://{interface_name}/{modport or 'full'}"
        if target != expected_target:
            raise SVXInheritanceError(
                f"virtual interface target {target!r} must be {expected_target!r}"
            )
        handle["operations"] = _vif_operations(target, fact, modport)

    def visit_class(declaration: object) -> None:
        if not isinstance(declaration, dict):
            return
        constructor = declaration.get("constructor")
        groups: list[object] = [constructor.get("parameters", [])] if isinstance(constructor, dict) else []
        for method in declaration.get("methods", []):
            if not isinstance(method, dict):
                continue
            groups.append(method.get("parameters", []))
            enrich_handle(method.get("return_handle"))
        for parameters in groups:
            if not isinstance(parameters, list):
                continue
            for parameter in parameters:
                if isinstance(parameter, dict):
                    enrich_handle(parameter.get("handle"))
        for base in declaration.get("base_lineage", []):
            visit_class(base)

    for declaration in classes:
        visit_class(declaration)


def _class_declaration(cls: Any) -> dict[str, Any]:
    """Render a normalized class without recursively rendering its lineage."""

    declaration: dict[str, Any] = {
        "canonical_id": cls.canonical_id,
        "language": cls.language,
        "symbol": cls.symbol,
        "methods": [],
    }

    def handle_declaration(handle: Any) -> dict[str, Any]:
        result = {
            "kind": handle.kind,
            "target_type_name": handle.target_type_name,
            "sv_type": handle.sv_type,
        }
        if handle.operations:
            result["operations"] = [
                {
                    "operation": operation.operation,
                    "member": operation.sv_member_name,
                    "method": {
                        "canonical_id": operation.method.canonical_id,
                        "name": operation.method.name,
                        "parameters": [parameter_declaration(item) for item in operation.method.parameters],
                        "return_type": (
                            operation.method.return_type.runtime_spec()
                            | {
                                "sv": operation.method.return_type.sv,
                                "sv_packer": operation.method.return_type.sv_packer,
                            }
                            if operation.method.return_type is not None
                            else "void"
                        ),
                        "timing": operation.method.timing,
                        "virtual": False,
                        "pure_virtual": False,
                    },
                }
                for operation in handle.operations
            ]
        return result

    def parameter_declaration(parameter: Any) -> dict[str, Any]:
        result = {
            "name": parameter.name,
            "type": parameter.type_binding.runtime_spec()
            | {
                "sv": parameter.type_binding.sv,
                "sv_packer": parameter.type_binding.sv_packer,
            },
            "direction": parameter.direction,
        }
        if parameter.handle is not None:
            result["handle"] = handle_declaration(parameter.handle)
        return result
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
            "parameters": [parameter_declaration(parameter) for parameter in cls.constructor.parameters],
        }
    for method in cls.methods:
        method_declaration = {
            "canonical_id": method.canonical_id,
            "name": method.name,
            "parameters": [parameter_declaration(parameter) for parameter in method.parameters],
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
        if method.return_handle is not None:
            method_declaration["return_handle"] = handle_declaration(method.return_handle)
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


def enrich_virtual_interface_manifest(
    manifest: Manifest, *, sv_source_files: Iterable[Path]
) -> Manifest:
    """Attach generated VIF views to an existing normalized manifest.

    ``inheritance-gen`` accepts a checked-in manifest as its stable input.
    This helper lets that command additionally inspect the SV interface source
    without requiring a second user-maintained VIF member whitelist.
    """

    paths = tuple(Path(path) for path in sv_source_files)
    if not paths:
        return manifest
    declaration = manifest_dict(manifest)
    _enrich_virtual_interface_handles(
        declaration["classes"], scan_sv_virtual_interfaces(paths)
    )
    return parse_manifest(declaration)
