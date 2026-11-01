"""Declaration front ends that normalize cross-language classes to a manifest."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from functools import wraps
from dataclasses import dataclass, replace
import inspect
import json
from pathlib import Path
import re
import sys
import weakref
from types import ModuleType
from typing import TYPE_CHECKING, Annotated, Any, Callable, Generic, Iterable, TypeAlias, TypeVar

from .errors import SVXInheritanceError
from ._svtypes_contract import require_type_spec_api
from .sv_source_options import _source_parse_options
from .sv_instance_scan import with_instance_discovery
from .inheritance import (
    EXTERNAL_FIELD_STORAGE_CAPABILITY,
    GENERATOR_ABI_VERSION,
    REQUIRED_RUNTIME_CAPABILITIES,
    SCHEMA_URI,
    SCHEMA_VERSION,
    Manifest,
    _codec_from_spec,
    _remote_ref_target,
    _type_binding,
    parse_manifest,
)
from .sv_scan import SVVirtualInterfaceFact, discover_sv_class_declarations, normalize_sv_handle_types, resolve_sv_field_handles, scan_sv_sources, scan_sv_virtual_interfaces, validate_sv_declarations

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

    require_type_spec_api(svtypes)
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
        owner = (cls.__module__, cls.__name__, name)
        if existing is not None and getattr(existing, "__svx_field_factory_owner__", None) != owner:
            raise SVXInheritanceError(
                f"inheritance codec factory name {cls.__module__}.{factory_name} is unavailable"
            )
        # Refresh the template when an iterative discovery process redefines
        # the class; a module reload preserves old globals by default.
        def factory(template=descriptor):
            return copy.deepcopy(template)

        factory.__name__ = factory_name
        factory.__qualname__ = factory_name
        factory.__svx_field_factory_owner__ = owner
        setattr(module, factory_name, factory)
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

    Empty source declarations acquire a generated implementation as their base.
    This common base owns no foreign object by itself: construction/binding is a
    generated lifecycle operation, not a side effect of importing a stub.
    """

    _svx_remote_object_id: int | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._svx_guard_source_initializer()

    @classmethod
    def _svx_guard_source_initializer(cls) -> None:
        if not getattr(cls, '__svx_guard_descendant_initializers__', False):
            return
        initializer = cls.__dict__.get('__init__')
        if initializer is None or getattr(initializer, '__svx_initializer_guard__', False):
            return

        @wraps(initializer)
        def initialize(instance, *args, **kwargs):
            depth = getattr(instance, '_svx_initializer_depth', 0)
            was_bound = getattr(instance, '_svx_remote_object_id', None) is not None
            instance._svx_initializer_depth = depth + 1
            try:
                return initializer(instance, *args, **kwargs)
            except BaseException as error:
                # Factory-stage failures already have their own rollback. This
                # catches the outer Python body after its SV super returned.
                if (depth == 0 and not was_bound
                        and getattr(instance, '_svx_target_constructor_completed', False)):
                    from .inheritance import close_instance

                    for action, cleanup in (
                        ('close projected storage', instance._svx_release_projected_fields),
                        ('close paired SV target', lambda: close_instance(instance)),
                    ):
                        try:
                            cleanup()
                        except BaseException as cleanup_error:
                            error.add_note(f'construction could not {action}: {cleanup_error}')
                raise
            finally:
                instance._svx_initializer_depth = depth

        initialize.__svx_initializer_guard__ = True
        cls.__init__ = initialize

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        for base in type(self).__mro__:
            declaration = base.__dict__.get('__svx_sv_mirror__')
            if (isinstance(declaration, dict)
                    and declaration['canonical_id'] not in _source_mirror_implementations):
                raise SVXInheritanceError(
                    f"generated mirror for {declaration['canonical_id']} is not loaded")
        super().__init__(*args, **kwargs)

    def _svx_bind_remote_object(self, object_id: int) -> None:
        if (not isinstance(object_id, int) or isinstance(object_id, bool)
                or not 0 < object_id < (1 << 64)):
            raise ValueError("SVX mirror object id must be an unsigned non-zero 64-bit integer")
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
            storage=getattr(self, "_svx_field_storage", None),
        )

    def _svx_release_projected_fields(self) -> None:
        """Detach external fields before the paired SV object is released."""

        from .inheritance import _retire_python_receiver_reservation

        _retire_python_receiver_reservation(self)

        storage = getattr(self, "_svx_field_storage", None)
        try:
            if storage is not None:
                storage.close()
        finally:
            try:
                session = self.codec_session
                number = self.svtypes_object_number
            except AttributeError:
                # Reservation can fail before SvTypes initializes the owner.
                pass
            else:
                if session.get(number) is self:
                    session.remove(number)
        # Keep projected fields bound to the closed backend. Detaching would
        # silently resurrect their pre-binding Python-local values.

    def _svx_retire_failed_python_companion(self, initialization_error: BaseException) -> None:
        from .inheritance import unbind_instance

        for action, cleanup in (
            ("close projected storage", self._svx_release_projected_fields),
            ("unbind Python companion", lambda: unbind_instance(self._svx_remote_object_id)),
        ):
            try:
                cleanup()
            except BaseException as cleanup_error:
                initialization_error.add_note(f"construction could not {action}: {cleanup_error}")


class _PythonRootOwner(SVMirror):
    """Private owner portion for generated companions of Python-root classes.

    Generated companions place the source class before this portion in their
    MRO. Its normal super call initializes SvTypes in the source constructor's
    coverage context, then binds projected fields before user code resumes.
    """

    __svx_root_field_ids__: dict[str, str] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if getattr(self, "_svx_root_owner_initialized", False):
            return
        if getattr(self, '_svx_reserved_owner_prepared', False):
            self._svx_reserved_owner_prepared = False
            self._svx_root_owner_initialized = True
            return
        super().__init__(*args, **kwargs)
        self._svx_root_owner_initialized = True
        if self.__svx_root_field_ids__:
            self._svx_bind_projected_fields(self.__svx_root_field_ids__)

    @classmethod
    def __svx_create_from_sv__(cls, remote_object_id: int, *args: Any):
        from .inheritance import bind_instance

        instance = cls.__new__(cls)
        instance._svx_bind_remote_object(remote_object_id)
        # A failed bind must not retire a different object already using the ID.
        bind_instance(remote_object_id, instance)
        try:
            cls.__init__(instance, *args)
            if not getattr(instance, "_svx_root_owner_initialized", False):
                raise SVXInheritanceError(
                    "Python-root companion initializer did not initialize its SvTypes owner"
                )
        except BaseException as initialization_error:
            SVMirror._svx_retire_failed_python_companion(instance, initialization_error)
            raise
        return instance


_source_mirror_declarations: dict[str, weakref.WeakSet] = {}
_source_mirror_implementations: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


def _install_source_mirror(source: type, implementation: type) -> None:
    if source.__bases__ == (implementation,):
        return
    if source.__bases__ != (SVMirror,):
        raise SVXInheritanceError(
            f"source mirror {source.__module__}.{source.__name__} must directly extend SVMirror")
    refresh = getattr(SvObject, 'refresh_declarations', None)
    if not callable(refresh):
        raise SVXInheritanceError(
            'source mirror binding requires SvTypes SvObject.refresh_declarations()')
    try:
        # Keep the source class identity: already defined children and their
        # zero-argument super() must see the same newly executable base.
        source.__bases__ = (implementation,)
    except TypeError as error:
        raise SVXInheritanceError(
            f"cannot install generated mirror for {source.__module__}.{source.__name__}: {error}") from error
    pending = [source]
    while pending:
        child = pending.pop()
        refresh.__func__(child)
        child._svx_guard_source_initializer()
        pending.extend(child.__subclasses__())
    if "__init_subclass__" in implementation.__dict__:
        from .inheritance import register_python_subclass
        class_id = source.__dict__["__svx_sv_mirror__"]["canonical_id"]
        for child in source.__subclasses__():
            register_python_subclass(class_id, child)


def _register_source_mirror_implementation(class_id: str, implementation: type) -> None:
    if (not issubclass(implementation, SVMirror)
            or implementation.__dict__.get("__svx_foreign_class_id__") != class_id):
        raise SVXInheritanceError(f"invalid generated source mirror implementation for {class_id}")
    previous = _source_mirror_implementations.get(class_id)
    if (previous is not None and previous is not implementation
            and _source_mirror_declarations.get(class_id)):
        raise SVXInheritanceError(f"conflicting generated source mirror implementation for {class_id}")
    for source in tuple(_source_mirror_declarations.get(class_id, ())):
        _install_source_mirror(source, implementation)
    _source_mirror_implementations[class_id] = implementation


def sv_mirror(canonical_id: str):
    """Mark an ``SVMirror`` source class as the static view of one SV class.

    The decorator does not generate code or allocate an SV instance. Discovery
    matches the ID to the SV declaration. At runtime, loading the matching
    generated mirror installs its behavior without replacing source class identity.
    """

    if not isinstance(canonical_id, str) or not canonical_id.startswith("sv://"):
        raise ValueError("sv_mirror canonical_id must be an sv:// identifier")

    def decorate(cls: type):
        if not isinstance(cls, type) or not issubclass(cls, SVMirror):
            raise TypeError("sv_mirror() requires an SVMirror subclass")
        if "__svx_sv_mirror__" in cls.__dict__:
            raise SVXInheritanceError(f"SV mirror {cls.__name__} is already declared")
        setattr(cls, "__svx_sv_mirror__", {"canonical_id": canonical_id})
        _source_mirror_declarations.setdefault(canonical_id, weakref.WeakSet()).add(cls)
        implementation = _source_mirror_implementations.get(canonical_id)
        if implementation is not None:
            _install_source_mirror(cls, implementation)
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


def _constructor_declarations_from_annotations(cls: type) -> list[dict[str, Any]]:
    initializer = cls.__dict__.get("__init__")
    if initializer is None:
        return []
    signature = list(inspect.signature(initializer).parameters.values())
    annotations = _resolved_annotations(initializer)
    if not any(parameter.name in annotations for parameter in signature[1:]):
        return []
    where = f"inheritance constructor {cls.__name__}.__init__"
    if not signature or signature[0].name != "self":
        raise SVXInheritanceError(f"{where} must begin with self")
    declarations: list[dict[str, Any]] = []
    for parameter in signature[1:]:
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            raise SVXInheritanceError(
                f"{where}.{parameter.name}: automatic constructor discovery requires "
                "fixed positional parameters"
            )
        annotation = annotations.get(parameter.name, inspect.Signature.empty)
        if annotation is inspect.Signature.empty:
            raise SVXInheritanceError(f"{where} must annotate every non-self parameter")
        if isinstance(annotation, _ParameterMarker):
            if annotation.direction != "input":
                raise SVXInheritanceError(f"{where}.{parameter.name} must be input")
            annotation = annotation.type_declaration
        declarations.append(inheritance_parameter(
            parameter.name,
            _type_declaration(annotation, where=f"{where}.{parameter.name}"),
        ))
    return declarations


def inheritance_class(
    *,
    canonical_id: str | None = None,
    constructor_parameters: Iterable[dict[str, Any]] | None = None,
    constructor_initiator: str = "python",
    base_lineage: Iterable[dict[str, Any]] | None = None,
    specialization: dict[str, Any] | None = None,
):
    """Declare a target, inferring an annotated own initializer unless overridden."""

    explicit_parameters = (
        list(constructor_parameters) if constructor_parameters is not None else None
    )
    normalized_lineage = list(base_lineage or ())

    def decorate(cls: type):
        if not isinstance(cls, type):
            raise TypeError("inheritance_class() may only decorate a class")
        if "<locals>" in cls.__qualname__ or "." in cls.__qualname__:
            raise SVXInheritanceError("nested Python inheritance classes are unsupported")
        class_id = canonical_id or f"py://{cls.__module__.replace('.', '/')}/{cls.__name__}"
        constructor = {
            "initiator": constructor_initiator,
            "parameters": (
                list(explicit_parameters) if explicit_parameters is not None
                else _constructor_declarations_from_annotations(cls)
            ),
        }
        mirror_bases = [
            base.__dict__["__svx_sv_mirror__"]["canonical_id"]
            for base in cls.__bases__
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
                "python_base_ids": [
                    base.__dict__["__svx_inheritance_class__"]["canonical_id"]
                    for base in cls.__bases__
                    if "__svx_inheritance_class__" in base.__dict__
                ],
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


from .sv_value_scan import SourceValues, with_value_discovery
from .value_exports import with_value_types


@with_value_discovery
@with_instance_discovery
def manifest_from_declarations(
    *,
    python_modules: Iterable[ModuleType] = (),
    sv_declaration_files: Iterable[Path] = (),
    sv_source_files: Iterable[Path] = (),
    sv_predefines: Mapping[str, str | None] | None = None,
    sv_undefines: Iterable[str] = (),
    sv_compilation_unit: bool = False,
    sv_include_dirs: Iterable[Path] = (),
    sv_class_targets: Iterable[str] = (),
    sv_package_targets: Iterable[str] = (),
    sv_recursive_packages: bool = False,
    sv_exclude_classes: Iterable[str] = (),
    sv_member_targets: Iterable[str] = (),
    sv_exclude_members: Iterable[str] = (),
    sv_type_targets: Iterable[str] = (),
    sv_exclude_types: Iterable[str] = (),
    sv_constant_targets: Iterable[str] = (),
    sv_exclude_constants: Iterable[str] = (),
    sv_callable_targets: Iterable[str] = (),
    sv_exclude_callables: Iterable[str] = (),
) -> Manifest:
    """Normalize supported declaration front ends to the sole v2 manifest model."""

    sv_source_files = tuple(sv_source_files)
    sv_class_targets = tuple(sv_class_targets)
    sv_package_targets = tuple(sv_package_targets)
    sv_exclude_classes = tuple(sv_exclude_classes)
    sv_member_targets = tuple(sv_member_targets)
    sv_exclude_members = tuple(sv_exclude_members)
    sv_type_targets = tuple(sv_type_targets)
    sv_exclude_types = tuple(sv_exclude_types)
    sv_constant_targets = tuple(sv_constant_targets)
    sv_exclude_constants = tuple(sv_exclude_constants)
    sv_callable_targets = tuple(sv_callable_targets)
    sv_exclude_callables = tuple(sv_exclude_callables)
    selecting_sv = bool(sv_class_targets or sv_package_targets)
    direct_selection = bool(selecting_sv or sv_type_targets or sv_constant_targets or sv_callable_targets)
    if sv_exclude_callables and not (sv_package_targets or sv_callable_targets):
        raise SVXInheritanceError('SV callable exclusions require package or callable selectors')
    if sv_exclude_types and not direct_selection:
        raise SVXInheritanceError('SV type exclusions require class, package, type or constant selectors')
    if sv_exclude_constants and not (sv_package_targets or sv_constant_targets):
        raise SVXInheritanceError('SV constant exclusions require package or constant selectors')
    if (sv_member_targets or sv_exclude_members) and not selecting_sv:
        raise SVXInheritanceError('SV member selection requires class or package selectors')
    if (direct_selection or sv_recursive_packages or sv_exclude_classes) and not sv_source_files:
        raise SVXInheritanceError('SV export selection requires SV source files or original build inputs')
    if sv_recursive_packages and not sv_package_targets:
        raise SVXInheritanceError('recursive SV package export requires a package selector')
    if sv_exclude_classes and not selecting_sv:
        raise SVXInheritanceError('SV class exclusions require class or package selectors')
    sv_undefines = tuple(sv_undefines) if not isinstance(sv_undefines, str) else sv_undefines
    sv_include_dirs = tuple(sv_include_dirs) if not isinstance(sv_include_dirs, (str, bytes, Path)) else sv_include_dirs
    if (sv_predefines or sv_undefines or sv_compilation_unit or sv_include_dirs) and not sv_source_files:
        raise SVXInheritanceError("SV source configuration requires SV source files")
    parse_options = _source_parse_options(sv_predefines, sv_undefines, sv_include_dirs,
                                          discover_proxies=True) if sv_source_files else None
    # Nested method/handle dictionaries are intentionally enriched below;
    # never mutate decorator metadata retained on the user's Python classes.
    python_modules = tuple(python_modules)
    classes = [copy.deepcopy(item) for item in _python_declarations(python_modules)]
    # Ancestors provide discovery context, not additional generation targets.
    python_ancestors = {}
    for module in python_modules:
        for value in module.__dict__.values():
            if isinstance(value, type):
                for base in value.__mro__:
                    item = base.__dict__.get("__svx_inheritance_class__")
                    if isinstance(item, dict):
                        python_ancestors[item["canonical_id"]] = copy.deepcopy(item)
    sv_classes: list[dict[str, Any]] = []
    for path in sv_declaration_files:
        sv_classes.extend(load_sv_declarations(path))
    if not classes and not sv_classes and not direct_selection:
        details = []
        for module in python_modules:
            mirrors = sorted({value.__name__ for value in module.__dict__.values()
                              if isinstance(value, type)
                              and '__svx_sv_mirror__' in value.__dict__})
            defining_modules = sorted({value.__module__ for value in module.__dict__.values()
                                      if isinstance(value, type)
                                      and '__svx_inheritance_class__' in value.__dict__
                                      and value.__module__ != module.__name__})
            if mirrors:
                details.append(f'{module.__name__} contains Mirror stubs '
                               f'({", ".join(mirrors)}); stubs provide context, not export targets')
            if defining_modules:
                details.append(f'{module.__name__} re-exports declarations; select their defining '
                               f'--python-module: {", ".join(defining_modules)}')
        raise SVXInheritanceError(
            'no inheritance export targets discovered. '
            + ('; '.join(details) + '. ' if details else '')
            + 'Select a module defining @svx.inheritance_class() classes or provide '
            '--sv-declarations; --sv-source supplies parsing context, not target selection.'
        )
    sv_context = []
    auto_values = (SourceValues(_source_value_annotations(python_modules), sv_exclude_types,
                               sv_exclude_constants, sv_exclude_callables) if direct_selection else None)
    if sv_source_files:
        if auto_values is not None and (sv_type_targets or sv_constant_targets or sv_callable_targets or sv_package_targets):
            auto_values.select(sv_source_files, types=sv_type_targets, constants=sv_constant_targets,
                               callables=sv_callable_targets, packages=sv_package_targets,
                               recursive=sv_recursive_packages, parse_options=parse_options,
                               compilation_unit=sv_compilation_unit)
        class_analysis = bool(classes or sv_classes or selecting_sv or python_ancestors)
        source_facts = (scan_sv_sources(sv_source_files, allow_no_packages=True,
                                       parse_options=parse_options, compilation_unit=sv_compilation_unit)
                        if class_analysis else {})
        from .sv_instance_scan import needs_instance_analysis, prepare_instance_analysis
        instance_patterns = (*sv_class_targets, *(class_id for item in python_ancestors.values()
                              for class_id in item.get('mirror_base_ids', ()) if class_id.startswith('sv://instance/')))
        if needs_instance_analysis(sv_source_files, instance_patterns, parse_options=parse_options,
                                   compilation_unit=sv_compilation_unit):
            instance_analysis = prepare_instance_analysis(sv_source_files, parse_options=parse_options,
                                                           compilation_unit=sv_compilation_unit, patterns=instance_patterns)
            source_facts.update(instance_analysis.facts)
        interface_facts = (scan_sv_virtual_interfaces(sv_source_files, parse_options=parse_options,
                                                    compilation_unit=sv_compilation_unit)
                           if class_analysis or auto_values and auto_values.callables else {})
        _enrich_python_source_handles([*classes, *python_ancestors.values()], source_facts, interface_facts)
        explicit_ids = {item["canonical_id"] for item in sv_classes}
        selected_ids = ()
        if selecting_sv:
            from .sv_selection import select_sv_classes
            selected_ids = select_sv_classes(
                sv_source_files, source_facts, classes=sv_class_targets,
                packages=sv_package_targets, recursive=sv_recursive_packages,
                exclude=sv_exclude_classes, parse_options=parse_options,
                compilation_unit=sv_compilation_unit,
                allow_empty=bool(auto_values and (auto_values.declarations or auto_values.constants or auto_values.callables)))
        requested_ids = sorted({
            class_id for item in python_ancestors.values()
            for class_id in item.get("mirror_base_ids", [])
            if class_id not in explicit_ids
        } | (set(selected_ids) - explicit_ids))
        if requested_ids:
            value_annotations = _source_value_annotations(python_modules)
            sv_context = discover_sv_class_declarations(
                sv_source_files, requested_ids,
                lambda actual, *, where: _source_semantic_type_declaration(
                    actual, where=where, value_annotations=value_annotations, value_exports=auto_values),
                parse_options=parse_options, compilation_unit=sv_compilation_unit,
                existing=sv_classes,
                python_context=python_ancestors.values(),
                member_patterns=sv_member_targets,
                exclude_member_patterns=sv_exclude_members,
                value_exports=auto_values,
            )
            for declaration in sv_context:
                if declaration['canonical_id'] in selected_ids:
                    declaration['constructor']['initiator'] = 'python'
                    sv_classes.append(declaration)
            sv_context = [item for item in sv_context if item['canonical_id'] not in selected_ids]
    classes.extend(sv_classes)
    callable_context = ([{'language': 'python', 'symbol': 'SVXCallableContext',
                         'methods': [item['method'] for item in auto_values.callables.values()]}]
                        if auto_values and auto_values.callables else [])
    if sv_source_files and (classes or sv_context or callable_context):
        source_declarations = [*classes, *sv_context]
        _enrich_native_handle_fields(source_declarations, sv_source_files, parse_options=parse_options,
                                     compilation_unit=sv_compilation_unit, proxy_context=python_ancestors.values())
        normalize_sv_handle_types([*source_declarations, *callable_context], sv_source_files, parse_options=parse_options,
            compilation_unit=sv_compilation_unit, proxy_context=python_ancestors.values(),
            vif_enricher=_semantic_vif_enricher(interface_facts,
                value_annotations=_source_value_annotations(python_modules), value_exports=auto_values))
        validate_sv_declarations([*sv_classes, *sv_context], sv_source_files, parse_options=parse_options,
                                 compilation_unit=sv_compilation_unit, proxy_context=python_ancestors.values())
        _enrich_virtual_interface_handles([*source_declarations, *callable_context], interface_facts)
    declared_by_id = {**{item["canonical_id"]: item for item in sv_context}, **python_ancestors, **{
        item.get("canonical_id"): item
        for item in classes
        if isinstance(item, dict) and isinstance(item.get("canonical_id"), str)
    }}
    resolving = set()
    resolved = set()

    def resolve_lineage(declaration):
        class_id = declaration["canonical_id"]
        if class_id in resolved:
            return
        if class_id in resolving:
            raise SVXInheritanceError(f"cyclic discovery lineage at {class_id}")
        resolving.add(class_id)
        source_base_id = declaration.pop("discovery_base_id", None)
        mirror_base_ids = declaration.pop("mirror_base_ids", [])
        python_base_ids = declaration.pop("python_base_ids", [])
        base_ids = [source_base_id] if source_base_id is not None else mirror_base_ids or python_base_ids
        if not declaration.get("base_lineage") and base_ids:
            if len(base_ids) != 1:
                raise SVXInheritanceError("Python inheritance declaration has multiple logical bases")
            base = declared_by_id.get(base_ids[0])
            if not isinstance(base, dict):
                raise SVXInheritanceError(
                    f"Python mirror base {base_ids[0]!r} has no matching declaration"
                )
            resolve_lineage(base)
            inherited = base.get("base_lineage", [])
            if not isinstance(inherited, list):
                raise SVXInheritanceError("inheritance base has invalid base_lineage")
            direct = {key: value for key, value in base.items() if key != "base_lineage"}
            declaration["base_lineage"] = [*inherited, direct]
        if mirror_base_ids and python_base_ids:
            lineage_ids = {item.get("canonical_id")
                           for item in declaration.get("base_lineage", [])
                           if isinstance(item, dict)}
            missing = set(python_base_ids) - lineage_ids
            if missing:
                raise SVXInheritanceError(
                    f"Python class {class_id} has bases absent from its SV mirror lineage: "
                    + ", ".join(sorted(missing)))
        resolving.remove(class_id)
        resolved.add(class_id)

    for declaration in classes:
        resolve_lineage(declaration)
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
            "schema_version": ('2.7.0' if auto_values and any(item.default_class_owners for item in
                                           (*auto_values.declarations.values(), *auto_values.constants.values())) else
                               '2.6.0' if (auto_values and any((item.source_scope or {}).get('kind') == 'instance'
                                            for item in (*auto_values.declarations.values(), *auto_values.constants.values()))) or any((item.get('source_scope') or {}).get('kind') == 'instance' for cls in classes
                                           for item in (*cls.get('base_lineage', []), cls)) else
                               '2.5.0' if any(item.get('source_scope') is not None for cls in classes
                                             for item in (*cls.get('base_lineage', []), cls)) else
                               '2.4.0' if auto_values and any(item.source_scope is not None for item in
                               (*auto_values.declarations.values(), *auto_values.constants.values())) else
                               '2.3.0' if auto_values and auto_values.callables else
                               '2.2.0' if auto_values and auto_values.constants else
                               '2.1.0' if auto_values and auto_values.declarations else SCHEMA_VERSION),
            "generator_abi_version": GENERATOR_ABI_VERSION,
            "required_runtime_capabilities": required_capabilities,
            "classes": classes,
            **({'value_types': [item.as_dict() for item in auto_values.declarations.values()]}
               if auto_values and auto_values.declarations else {}),
            **({'constants': [item.as_dict() for item in auto_values.constants.values()]}
               if auto_values and auto_values.constants else {}),
            **({'callables': list(auto_values.callables.values())} if auto_values and auto_values.callables else {}),
        }
    )


def _source_value_annotations(modules) -> dict[str, tuple[type, ...]]:
    candidates = {}
    sources = set(modules)
    for module in modules:
        for value in module.__dict__.values():
            if isinstance(value, type):
                for base in value.__mro__:
                    owner = sys.modules.get(base.__module__)
                    if owner is not None:
                        sources.add(owner)
    for module in sources:
        for value in module.__dict__.values():
            if (not isinstance(value, type) or value in {svtypes.Enum, svtypes.SvStruct}
                    or not issubclass(value, (svtypes.Enum, svtypes.SvStruct))
                    or not svtypes.is_materializable_type(value)):
                continue
            codec = svtypes.materialize_type_spec(value, location="SV source value type")
            name = svtypes.sv_type_expression(codec)
            candidates.setdefault(name, set()).add(value)
    return {name: tuple(values) for name, values in candidates.items()}


def _validate_source_value_schema(actual, schema, *, where):
    actual = actual.canonicalType
    kind = schema["kind"]
    if kind in {"bits", "logic", "enum"}:
        if (not actual.isIntegral or actual.bitWidth != schema["width"]
                or actual.isSigned != schema["signed"]
                or actual.isFourState != (schema["state_domain"] == "4state")):
            raise SVXInheritanceError(f"{where} differs from the SvTypes value layout")
        if kind == "enum":
            if actual.kind.name != "EnumType":
                raise SVXInheritanceError(f"{where} is not the declared SvTypes enum")
            items = tuple((member.name, int(member.value.value)) for member in actual
                          if member.kind.name == "EnumValue" and not member.value.hasUnknown())
            if items != tuple(tuple(item) for item in schema["items"]):
                raise SVXInheritanceError(f"{where} enum members differ from the SvTypes declaration")
        return
    if kind == "struct" and actual.kind.name == "PackedStructType":
        members = tuple(member for member in actual if member.kind.name == "Field")
        fields = schema["fields"]
        if tuple(member.name for member in members) != tuple(field["name"] for field in fields):
            raise SVXInheritanceError(f"{where} struct members differ from the SvTypes declaration")
        for member, field in zip(members, fields):
            _validate_source_value_schema(member.type, field["type"], where=f"{where}.{member.name}")
        return
    raise SVXInheritanceError(f"{where} has no matching SvTypes value layout")


def _source_semantic_type_declaration(actual: Any, *, where: str,
                                      value_annotations=None, value_exports=None) -> dict[str, Any]:
    def annotation(source):
        original = source
        source = source.canonicalType
        if source.kind.name in {"EnumType", "PackedStructType", "UnpackedStructType"}:
            name = original.lexicalPath
            if value_exports is not None:
                return value_exports.annotation(original, where=where)
            candidates = (value_annotations or {}).get(name, ()) or (value_annotations or {}).get(
                name.rsplit("::", 1)[-1], ())
            if not candidates:
                canonical_name = source.lexicalPath
                candidates = (value_annotations or {}).get(canonical_name, ()) or (value_annotations or {}).get(
                    canonical_name.rsplit("::", 1)[-1], ())
            if len(candidates) != 1:
                raise SVXInheritanceError(
                    f"{where} requires one matching public SvTypes value declaration for {name}")
            candidate = candidates[0]
            _validate_source_value_schema(source, svtypes.schema_descriptor(candidate).schema, where=where)
            return candidate
        from .sv_scan import _source_handle_metadata
        handle = _source_handle_metadata(original, where=where, value_exports=value_exports)
        if handle is not None:
            return svtypes.RemoteRef[handle["target_type_name"]]
        kind = source.kind.name
        if kind in {"ScalarType", "PredefinedIntegerType"}:
            if str(source) == "int":
                return svtypes.Int
            if str(source) == "longint":
                return svtypes.LongInt
            factory = svtypes.Logic if source.isFourState else svtypes.Bit
            return factory[source.bitWidth, svtypes.Signed if source.isSigned else svtypes.Unsigned]
        if kind == "QueueType":
            if source.maxBound:
                raise SVXInheritanceError(
                    f"{where} bounded queue requires explicit declaration metadata"
                )
            return svtypes.Queue[annotation(source.elementType)]
        if kind == "DynamicArrayType":
            return svtypes.DynArray[annotation(source.elementType)]
        if kind == "FixedSizeUnpackedArrayType":
            if source.range.left != 0 or source.range.right != source.range.width - 1:
                raise SVXInheritanceError(
                    f"{where} unpacked range {source.range} requires explicit declaration metadata"
                )
            return svtypes.Array[annotation(source.elementType), source.range.width]
        if kind == "AssociativeArrayType":
            if source.indexType is None:
                raise SVXInheritanceError(
                    f"{where} wildcard associative index requires explicit declaration metadata"
                )
            return svtypes.AssocArray[annotation(source.indexType), annotation(source.elementType)]
        if kind == "PackedArrayType":
            dimensions = []
            element = source
            while element.kind.name == "PackedArrayType":
                if element.range.right != 0 or element.range.left != element.range.width - 1:
                    raise SVXInheritanceError(
                        f"{where} packed range {element.range} requires explicit declaration metadata"
                    )
                dimensions.append(element.range.width)
                element = element.elementType.canonicalType
            if str(element) not in {"bit", "logic", "bit signed", "logic signed"}:
                raise SVXInheritanceError(f"{where} packed element {element} requires explicit declaration metadata")
            factory = svtypes.Logic if source.isFourState else svtypes.Bit
            return factory[tuple(dimensions), svtypes.Signed if source.isSigned else svtypes.Unsigned]
        binding = _source_scalar_type_declaration(str(source), where=where)
        return svtypes.type_spec_from_identity(binding["svtypes"], location=where)

    selected_annotation = annotation(actual)
    result = _svtypes_binding(selected_annotation, where=where)
    if actual.canonicalType.kind.name in {"ScalarType", "PredefinedIntegerType", "FloatingType"}:
        result["sv"] = str(actual.canonicalType)
    elif actual.kind.name == "TypeAlias" and actual.canonicalType.kind.name in {
        "QueueType", "DynamicArrayType", "FixedSizeUnpackedArrayType", "AssociativeArrayType",
        "EnumType", "PackedStructType", "UnpackedStructType",
    }:
        from .sv_scan import _semantic_class_selector, _unit_scope
        selector = _semantic_class_selector(actual)
        unit = _unit_scope(selector)
        result["sv"] = '$unit::' + unit[1] if unit is not None else actual.lexicalPath
        if value_exports is not None:
            symbol, scope = value_exports.source_symbol(actual)
            if scope is None or scope['kind'] == 'compilation_unit':
                result['sv'] = value_exports.native_reference(actual)
    if (value_exports is not None and value_exports.current_instance is not None
            and (actual.kind.name == 'TypeAlias' or actual.canonicalType.kind.name in {'EnumType', 'PackedStructType'})):
        symbol, scope = value_exports.source_symbol(actual)
        if scope is not None and scope['kind'] == 'instance':
            from .value_exports import value_key
            if value_key(symbol, scope) not in value_exports.declarations:
                value_exports._add(symbol, selected_annotation, scope)
            result['sv'] = symbol
    return result


def _source_scalar_type_declaration(sv_type: str, *, where: str) -> dict[str, Any]:
    """Map the supported static SV scalar subset to a public SvTypes type."""

    normalized = " ".join(sv_type.split())
    def binding(annotation):
        result = _svtypes_binding(annotation, where=where)
        result["sv"] = normalized
        return result

    match = re.fullmatch(r"(bit|logic)(?:\s+(signed|unsigned))?\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?", normalized)
    if match:
        base, sign, left, right = match.groups()
        width = 1 if left is None else abs(int(left) - int(right)) + 1
        annotation = (svtypes.Bit if base == "bit" else svtypes.Logic)[
            width, svtypes.Signed if sign == "signed" else svtypes.Unsigned]
        return binding(annotation)
    scalar_types = {
        "int": svtypes.Int,
        "integer": svtypes.Logic[32, svtypes.Signed],
        "longint": svtypes.LongInt,
        "string": svtypes.String,
        "real": svtypes.Real,
        "shortreal": svtypes.ShortReal,
        "realtime": svtypes.RealTime,
        "time": svtypes.Logic[64],
    }
    annotation = scalar_types.get(normalized)
    integral = re.fullmatch(r"(byte|shortint|int|longint|integer|time)(?:\s+(signed|unsigned))?", normalized)
    if annotation is None and integral:
        base, sign = integral.groups()
        width = {"byte": 8, "shortint": 16, "int": 32, "longint": 64,
                 "integer": 32, "time": 64}[base]
        signed = sign == "signed" or (sign is None and base != "time")
        factory = svtypes.Logic if base in {"integer", "time"} else svtypes.Bit
        annotation = factory[width, svtypes.Signed if signed else svtypes.Unsigned]
    if annotation is None:
        raise SVXInheritanceError(
            f"{where} uses {sv_type!r}, which has no declared SvTypes source mapping; "
            "provide explicit declaration metadata"
        )
    return binding(annotation)


def _vif_type_declaration(sv_type: str, *, where: str) -> dict[str, Any]:
    try:
        return _source_scalar_type_declaration(sv_type, where=where)
    except SVXInheritanceError as error:
        raise SVXInheritanceError(str(error).replace("SvTypes source mapping", "SvTypes VIF mapping")) from error


def _vif_operations(
    target_type_name: str,
    fact: SVVirtualInterfaceFact,
    modport: str | None,
    *, native_scope=None, type_binding=None,
) -> list[dict[str, Any]]:
    if modport is not None and modport not in fact.modports:
        raise SVXInheritanceError(
            f"SystemVerilog interface {fact.symbol} has no modport {modport}"
        )
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
    def member_type(member, *, parameter=None, where):
        if native_scope is None:
            return _vif_type_declaration(parameter.sv_type if parameter is not None else member.sv_type, where=where)
        actual = native_scope.lookupName(member.name)
        if actual is None:
            raise SVXInheritanceError(f'{where} was not resolved in the static interface type')
        if parameter is not None:
            actual = next((argument.type for argument in actual.arguments if argument.name == parameter.name), None)
        else:
            actual = actual.type if member.kind == 'signal' else actual.returnType
        if actual is None or actual.isError:
            raise SVXInheritanceError(f'{where} has an unresolved type; supply its source dependencies')
        element = actual.canonicalType
        while element.isArray:
            element = element.arrayElementType.canonicalType
        if element.isClass or element.isVirtualInterface:
            raise SVXInheritanceError(
                f'{where} requires native handle binding inside a VIF operation; this layout remains unfinished')
        # Keep published builtin identities (width versus singleton dimensions).
        spelling = parameter.sv_type if parameter is not None else member.sv_type
        try:
            return _vif_type_declaration(spelling, where=where)
        except SVXInheritanceError:
            return type_binding(actual, where=where)

    for member in fact.members:
        direction = directions.get(member.name)
        if direction is None:
            continue
        if member.kind == "signal":
            assert member.sv_type is not None
            binding = member_type(
                member,
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
                            "timing": "function",
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
                    "type": member_type(
                        member, parameter=parameter,
                        where=f"virtual interface {fact.symbol}.{member.name}.{parameter.name}",
                    ),
                    "direction": parameter.direction,
                }
            )
        return_type: Any = "void"
        if member.kind == "function" and member.sv_type != "void":
            assert member.sv_type is not None
            return_type = member_type(
                member,
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


def _enrich_python_source_handles(classes, facts, interfaces):
    def enrich(member, type_key="type", handle_key="handle"):
        if member.get(handle_key) is not None or not isinstance(member.get(type_key), dict):
            return
        binding = _type_binding(member[type_key], "Python source handle", allow_void=False)
        if not isinstance(_codec_from_spec(binding.runtime_spec()), svtypes.RemoteRef):
            return
        target = _remote_ref_target(binding, "Python source handle")
        if target.startswith("sv://"):
            symbol = target.removeprefix("sv://").replace("/", "::")
            fact = facts.get(symbol)
            if fact is not None:
                if fact.parameter_kinds:
                    raise SVXInheritanceError(f"Python source handle {target} requires explicit closed class-handle target metadata")
                member[handle_key] = sv_class_handle(target, symbol)
        elif target.startswith("sv-vif://"):
            parts = target.removeprefix("sv-vif://").split("/")
            if len(parts) == 2 and parts[0] in interfaces:
                suffix = "" if parts[1] == "full" else "." + parts[1]
                member[handle_key] = virtual_interface_handle(target, "virtual " + parts[0] + suffix)

    for declaration in classes:
        if declaration.get("language") != "python":
            continue
        for field in declaration.get("fields", []):
            enrich(field)
        for parameter in (declaration.get("constructor") or {}).get("parameters", []):
            enrich(parameter)
        for method in declaration.get("methods", []):
            for parameter in method.get("parameters", []):
                enrich(parameter)
            enrich(method, "return_type", "return_handle")


def _enrich_native_handle_fields(classes: list[dict[str, Any]], paths: Iterable[Path], *, parse_options=None,
                                 compilation_unit=False, proxy_context=()) -> None:
    """Discover static member endpoints without selecting additional fields/classes."""

    paths = tuple(paths)
    from .sv_scan import _python_proxy_context
    proxy_context = tuple(proxy_context) or _python_proxy_context(classes)
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=proxy_context)
    selected = []

    def visit(declaration: object) -> None:
        if not isinstance(declaration, dict):
            return
        for base in declaration.get("base_lineage", []):
            visit(base)
        if declaration.get("language") != "sv":
            return
        from .sv_scan import _declaration_source_symbol
        fact = facts.get(_declaration_source_symbol(declaration))
        if fact is None:
            return  # Interface-only source inputs remain valid.
        fields = []
        for field in declaration.get("fields", []):
            if not isinstance(field, dict):
                continue
            where = f"SV field {declaration['symbol']}.{field.get('name')}"
            binding = _type_binding(field.get("type"), where, allow_void=False)
            assert binding is not None
            # A SvTypes object value can also have an SV class type. Only the
            # RemoteRef contract requests native-handle inference; do not turn
            # by-value object fields into handles because of their SV spelling.
            if field.get("handle") is not None or isinstance(_codec_from_spec(binding.runtime_spec()), svtypes.RemoteRef):
                fields.append(field)
        if fields:
            selected.append({**declaration, "fields": fields})

    for declaration in classes:
        visit(declaration)
    handles = resolve_sv_field_handles(selected, paths, parse_options=parse_options,
                                       compilation_unit=compilation_unit, proxy_context=proxy_context) if selected else {}
    for declaration in selected:
        for field in declaration.get("fields", []):
            if not isinstance(field, dict):
                continue
            metadata = handles.get((id(declaration), field.get("name")))
            if metadata is None:
                continue
            where = f"SV field {declaration['symbol']}.{field['name']}"
            binding = _type_binding(field.get("type"), where, allow_void=False)
            assert binding is not None
            target = _remote_ref_target(binding, where)
            handle = {**metadata, "target_type_name": target}
            existing = field.get("handle")
            if existing is not None:
                if not isinstance(existing, dict) or any(existing.get(key) != handle[key] for key in ("kind", "target_type_name")):
                    raise SVXInheritanceError(f"{where} handle metadata disagrees with its source type")
                # Keep an explicitly supplied equivalent type spelling. Other
                # members of the same target may use that alias as their shared
                # endpoint contract; normalizing only this field would split it.
            else:
                field["handle"] = handle


def _semantic_vif_enricher(facts, *, value_annotations=None, value_exports=None):
    operations = {}
    def binding(actual, *, where):
        return _source_semantic_type_declaration(actual, where=where,
            value_annotations=value_annotations, value_exports=value_exports)
    def enrich(handle, scope):
        if handle.get('operations'):
            return
        target = handle['target_type_name']
        if target not in operations:
            _enrich_vif_handle(handle, facts, native_scope=scope, type_binding=binding)
            operations[target] = copy.deepcopy(handle['operations'])
        else:
            handle['operations'] = copy.deepcopy(operations[target])
    return enrich


def _enrich_vif_handle(handle, facts, *, native_scope=None, type_binding=None):
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
        raise SVXInheritanceError(f"virtual interface {interface_name} was not found in scanned SV sources")
    expected_target = f"sv-vif://{interface_name}/{modport or 'full'}"
    if target != expected_target:
        raise SVXInheritanceError(f"virtual interface target {target!r} must be {expected_target!r}")
    handle["operations"] = _vif_operations(target, fact, modport, native_scope=native_scope,
                                           type_binding=type_binding)


def _enrich_virtual_interface_handles(
    classes: list[dict[str, Any]], facts: dict[str, SVVirtualInterfaceFact]
) -> None:
    """Attach generated VIF operations to handle metadata in-place."""

    def enrich_handle(handle):
        _enrich_vif_handle(handle, facts)

    def visit_class(declaration: object) -> None:
        if not isinstance(declaration, dict):
            return
        constructor = declaration.get("constructor")
        for field in declaration.get("fields", []):
            if isinstance(field, dict):
                enrich_handle(field.get("handle"))
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
    if cls.source_scope is not None:
        declaration['source_scope'] = cls.source_scope

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
                **({"handle": handle_declaration(field.handle)} if field.handle is not None else {}),
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
    result = {
        "schema_uri": manifest.schema_uri,
        "schema_version": manifest.schema_version,
        "generator_abi_version": manifest.generator_abi_version,
        "required_runtime_capabilities": list(manifest.required_runtime_capabilities),
        "classes": classes,
    }
    if manifest.discovery_provenance is not None:
        result['discovery_provenance'] = manifest.discovery_provenance.as_dict()
    if manifest.value_types:
        result['value_types'] = [value.as_dict() for value in manifest.value_types]
    if manifest.constants:
        result['constants'] = [value.as_dict() for value in manifest.constants]
    if manifest.callables:
        from .package_exports import callable_owners
        methods = {method['canonical_id']: method for owner in callable_owners(manifest)
                   for method in _class_declaration(owner)['methods']}
        result['callables'] = [{'symbol': item.symbol, 'method': methods[item.method.canonical_id]}
                               for item in manifest.callables]
    return result


@with_value_types
def enrich_virtual_interface_manifest(
    manifest: Manifest, *, sv_source_files: Iterable[Path],
    sv_predefines: Mapping[str, str | None] | None = None,
    sv_undefines: Iterable[str] = (),
    sv_compilation_unit: bool = False,
    sv_include_dirs: Iterable[Path] = (),
) -> Manifest:
    """Attach generated VIF views to an existing normalized manifest.

    ``inheritance-gen`` accepts a checked-in manifest as its stable input.
    This helper lets that command additionally inspect the SV interface source
    without requiring a second user-maintained VIF member whitelist.
    """

    paths = tuple(Path(path) for path in sv_source_files)
    sv_undefines = tuple(sv_undefines) if not isinstance(sv_undefines, str) else sv_undefines
    sv_include_dirs = tuple(sv_include_dirs) if not isinstance(sv_include_dirs, (str, bytes, Path)) else sv_include_dirs
    if (sv_predefines or sv_undefines or sv_compilation_unit or sv_include_dirs) and not paths:
        raise SVXInheritanceError("SV source configuration requires SV source files")
    if not paths:
        return manifest
    parse_options = _source_parse_options(sv_predefines, sv_undefines, sv_include_dirs,
                                          discover_proxies=True)
    if not manifest.classes and not manifest.callables:
        return manifest
    declaration = manifest_dict(manifest)
    if manifest.classes:
        _enrich_native_handle_fields(declaration["classes"], paths, parse_options=parse_options, compilation_unit=sv_compilation_unit)
    contexts = [*declaration['classes'], {'language': 'python', 'symbol': 'SVXCallableContext',
                'methods': [item['method'] for item in declaration.get('callables', [])]}]
    facts = scan_sv_virtual_interfaces(paths, parse_options=parse_options, compilation_unit=sv_compilation_unit)
    normalize_sv_handle_types(contexts, paths, parse_options=parse_options, compilation_unit=sv_compilation_unit,
                               vif_enricher=_semantic_vif_enricher(facts))
    _enrich_virtual_interface_handles(contexts, facts)
    # The input object has already passed file-backed provenance validation.
    # Enrichment is an in-memory derivative, not a new discovery certification.
    declaration.pop('discovery_provenance', None)
    return replace(parse_manifest(declaration), discovery_provenance=manifest.discovery_provenance)
