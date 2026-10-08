"""Opt-in declarations for the temporary UVMX bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import re
from types import MappingProxyType
from typing import Any, Callable

import svx.inheritance
from svx.callback_context import blocking_operations_disallowed


_SV_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
_SV_QUALIFIED_TYPE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_$]*::)*[A-Za-z_][A-Za-z0-9_$]*\Z"
)
_CANONICAL_ID = re.compile(r"py://[^\s#]+\Z")
_FUNCTION_PHASES = (
    "build_phase",
    "connect_phase",
    "end_of_elaboration_phase",
    "start_of_simulation_phase",
)
_TASK_PHASES = ("run_phase",)
_SUPPORTED_PHASES = frozenset((*_FUNCTION_PHASES, *_TASK_PHASES))


@dataclass(frozen=True, slots=True)
class UvmTestDeclaration:
    """Complete declarative description of one generated UVM test proxy."""

    canonical_id: str
    sv_base: str
    factory_name: str
    python_type: type["Test"]

    @property
    def module(self) -> str:
        return self.python_type.__module__

    @property
    def qualname(self) -> str:
        return self.python_type.__qualname__

    @property
    def function_phases(self) -> tuple[str, ...]:
        return tuple(name for name in _FUNCTION_PHASES if name in self.python_type.__dict__)

    @property
    def task_phases(self) -> tuple[str, ...]:
        return tuple(name for name in _TASK_PHASES if name in self.python_type.__dict__)


_DECLARATIONS_BY_ID: dict[str, UvmTestDeclaration] = {}
_DECLARATIONS_BY_FACTORY: dict[str, UvmTestDeclaration] = {}


def _empty_contract(method_id: str) -> dict[str, dict[str, Any]]:
    return {
        method_id: {
            "parameters": (),
            "request": (),
            "response": (),
        }
    }


def _validate_phase_signature(cls: type["Test"], name: str) -> None:
    method = cls.__dict__.get(name)
    if method is None:
        return
    if isinstance(method, (staticmethod, classmethod)) or not callable(method):
        raise TypeError(f"{cls.__name__}.{name} must be an instance method")
    parameters = tuple(inspect.signature(method).parameters.values())
    if len(parameters) != 1 or parameters[0].kind not in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        raise TypeError(
            f"U0 phase {cls.__name__}.{name} must have exactly one self parameter"
        )


def _validate_constructor(cls: type["Test"]) -> None:
    initializer = cls.__dict__.get("__init__")
    if initializer is None:
        return
    parameters = tuple(inspect.signature(initializer).parameters.values())
    if len(parameters) != 1 or parameters[0].kind not in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        raise TypeError(
            f"U0 mapped test {cls.__name__} must have a no-user-argument __init__"
        )


def _validate_class(cls: type["Test"], canonical_id: str, sv_base: str, factory_name: str) -> None:
    if not isinstance(cls, type) or not issubclass(cls, Test):
        raise TypeError("@uvm_test requires a direct or indirect uvmx.Test subclass")
    if not _CANONICAL_ID.fullmatch(canonical_id):
        raise ValueError("canonical_id must be a non-empty py:// identifier without whitespace or '#'")
    if not _SV_IDENTIFIER.fullmatch(factory_name):
        raise ValueError(f"factory_name is not a legal SystemVerilog identifier: {factory_name!r}")
    if not _SV_QUALIFIED_TYPE.fullmatch(sv_base):
        raise ValueError(f"sv_base is not a legal SystemVerilog type name: {sv_base!r}")
    _validate_constructor(cls)
    for name, member in cls.__dict__.items():
        if name.endswith("_phase") and name not in _SUPPORTED_PHASES:
            raise TypeError(f"U0 does not support mapped phase {cls.__name__}.{name}")
    for phase in _SUPPORTED_PHASES:
        _validate_phase_signature(cls, phase)


class Test:
    """Base class for an opt-in Python UVM test proxy.

    UVM creates the paired SV component.  Its generated proxy calls
    :meth:`__svx_create_from_sv__`, which creates and binds this Python object
    before any mapped phase callback may run.
    """

    _uvmx_object_id: int

    def build_phase(self) -> None:
        pass

    def connect_phase(self) -> None:
        pass

    def end_of_elaboration_phase(self) -> None:
        pass

    def start_of_simulation_phase(self) -> None:
        pass

    def run_phase(self) -> None:
        pass

    def __svx_dispatch_foreign__(self, method_name: str, *arguments: object) -> object:
        """Apply the SV function-context rule to mapped U0 function phases."""

        method = getattr(self, method_name)
        if method_name in _FUNCTION_PHASES:
            with blocking_operations_disallowed(f"UVMX function phase {method_name}()"):
                return method(*arguments)
        return method(*arguments)

    @classmethod
    def __svx_create_from_sv__(cls, object_id: int) -> "Test":
        instance = cls.__new__(cls)
        instance._uvmx_object_id = object_id
        svx.inheritance.bind_instance(object_id, instance)
        try:
            # UVM's factory invokes proxy construction from an SV function.
            # The companion initializer therefore has the same no-blocking
            # rule as mapped function phases.
            with blocking_operations_disallowed("UVMX Python test construction"):
                cls.__init__(instance)
        except BaseException:
            svx.inheritance.unbind_instance(object_id)
            raise
        return instance


def uvm_test(
    *,
    canonical_id: str,
    sv_base: str = "uvm_pkg::uvm_test",
    factory_name: str,
) -> Callable[[type[Test]], type[Test]]:
    """Declare one Python test that the UVMX generator may project to SV."""

    def decorate(cls: type[Test]) -> type[Test]:
        _validate_class(cls, canonical_id, sv_base, factory_name)
        declaration = UvmTestDeclaration(canonical_id, sv_base, factory_name, cls)
        prior_id = _DECLARATIONS_BY_ID.get(canonical_id)
        if prior_id is not None and prior_id.python_type is not cls:
            raise ValueError(f"duplicate UVMX canonical_id: {canonical_id}")
        prior_factory = _DECLARATIONS_BY_FACTORY.get(factory_name)
        if prior_factory is not None and prior_factory.python_type is not cls:
            raise ValueError(f"duplicate UVMX factory_name: {factory_name}")
        _DECLARATIONS_BY_ID[canonical_id] = declaration
        _DECLARATIONS_BY_FACTORY[factory_name] = declaration
        setattr(cls, "__uvmx_declaration__", declaration)

        svx.inheritance.register_constructor(canonical_id, ())
        svx.inheritance.register_python_subclass(canonical_id, cls)
        for phase in _SUPPORTED_PHASES:
            svx.inheritance.register_contract(_empty_contract(f"{canonical_id}#{phase}"))
        return cls

    return decorate


def declared_tests(module_name: str | None = None) -> tuple[UvmTestDeclaration, ...]:
    """Return deterministic declarations, optionally limited to one module."""

    declarations = tuple(_DECLARATIONS_BY_ID.values())
    if module_name is not None:
        declarations = tuple(item for item in declarations if item.module == module_name)
    return tuple(sorted(declarations, key=lambda item: (item.factory_name, item.canonical_id)))


def declaration_registry() -> MappingProxyType[str, UvmTestDeclaration]:
    """Read-only view used by the bootstrap generator and its tests."""

    return MappingProxyType(_DECLARATIONS_BY_ID)
