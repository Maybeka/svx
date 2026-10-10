"""Public generation boundary for synchronous, callback-only SV integrations.

The generated endpoint owns SVX's private object and DPI plumbing. Consumers
declare no-argument callbacks and compose that endpoint into their SV class;
they do not implement dispatcher interfaces or manufacture call records.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
import re

from .errors import SVXInheritanceError


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_CLASS_ID = re.compile(r"py://[A-Za-z_][A-Za-z0-9_./]*\Z")
_RESERVED = frozenset({"new", "svx_invoke", "close", "__object_id"})


@dataclass(frozen=True)
class Callback:
    """One no-argument, no-return-value Python callback exposed to SV."""

    name: str
    timing: str

    def __post_init__(self) -> None:
        if not _IDENT.fullmatch(self.name) or self.name in _RESERVED:
            raise ValueError(f"invalid callback name: {self.name!r}")
        if self.timing not in {"function", "task"}:
            raise ValueError("callback timing must be 'function' or 'task'")


@dataclass(frozen=True)
class CallbackAdapter:
    """Generate an SV-owned Python companion for an external framework.

    Construction is a nonblocking SV function. A task callback may use ordinary
    SVX timing; a function callback cannot wait or start an SV process. Arguments,
    return values, fields and inheritance belong to the inheritance generator,
    not this deliberately callback-only extension interface.
    """

    class_id: str
    callbacks: tuple[Callback, ...]

    def __post_init__(self) -> None:
        if not _CLASS_ID.fullmatch(self.class_id):
            raise ValueError(f"invalid callback class ID: {self.class_id!r}")
        if not isinstance(self.callbacks, tuple) or not all(
            isinstance(item, Callback) for item in self.callbacks
        ):
            raise TypeError("callbacks must be a tuple of Callback declarations")
        names = [item.name for item in self.callbacks]
        if len(names) != len(set(names)):
            raise ValueError("callback names must be unique")

    def register_type(self, python_type: type) -> None:
        """Register the companion source without changing its Python prototype."""
        from . import inheritance
        from .callback_context import blocking_operations_disallowed

        if not isinstance(python_type, type):
            raise TypeError("callback companion must be a Python class")
        try:
            inspect.signature(python_type).bind()
        except TypeError as error:
            raise TypeError("callback companion requires no constructor arguments") from error
        for initializer in (python_type.__new__, python_type.__init__):
            if inspect.iscoroutinefunction(initializer) or inspect.isgeneratorfunction(initializer):
                raise TypeError("callback construction must execute synchronously")
        for callback in self.callbacks:
            descriptor = inspect.getattr_static(python_type, callback.name)
            if isinstance(descriptor, (staticmethod, classmethod)) or not callable(descriptor):
                raise TypeError(f"{callback.name} must be an instance method")
            if inspect.iscoroutinefunction(descriptor) or inspect.isgeneratorfunction(descriptor):
                raise TypeError(f"{callback.name} must execute synchronously")
            parameters = tuple(inspect.signature(descriptor).parameters.values())
            if len(parameters) != 1 or parameters[0].kind not in (
                inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD
            ):
                raise TypeError(f"{callback.name} must have exactly one self parameter")

        existing = _registered.get(self.class_id)
        if existing is not None:
            if existing[:2] != (self, python_type):
                raise SVXInheritanceError(f"conflicting callback companion for {self.class_id}")

        class CompanionFactory:
            @classmethod
            def __svx_create_from_sv__(cls, object_id: int) -> object:
                # Binding precedes initialization, just as generated mirrors do.
                with blocking_operations_disallowed("constructing an SV callback companion"):
                    instance = python_type.__new__(python_type)
                    inheritance.bind_instance(object_id, instance)
                    try:
                        python_type.__init__(instance)
                    except BaseException:
                        inheritance.unbind_instance(object_id)
                        raise
                return instance

        inheritance.register_constructor(self.class_id, ())
        inheritance.register_contract({
            f"{self.class_id}#{item.name}": {
                "parameters": (), "request": (), "response": (), "timing": item.timing
            }
            for item in self.callbacks
        })
        factory = existing[2] if existing is not None else CompanionFactory
        inheritance.register_python_subclass(self.class_id, factory)
        _registered[self.class_id] = (self, python_type, factory)

    def render_sv(self, class_name: str) -> str:
        """Render one adapter class inside the consumer's chosen SV package.

        The package must import svx_pkg. Instantiate this class from an SV function,
        then call its named methods. The companion remains alive until SVX shutdown;
        this API does not own the external framework's component lifecycle.
        """
        if not _IDENT.fullmatch(class_name):
            raise ValueError(f"invalid SV callback adapter name: {class_name!r}")
        quote = json.dumps
        lines = [
            "// Generated by svx.callbacks.CallbackAdapter. Do not edit.",
            f"class {class_name} implements svx_dispatchable;",
            "  local longint unsigned __object_id;",
            "  function new();",
            "    chandle request;",
            "    string error;",
            "    byte unsigned bytes[$];",
            "    __object_id = svx_inheritance_registry::allocate_object_id();",
            "    svx_inheritance_registry::register_object(__object_id, this);",
            '    request = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
            f"    if (!svx_inheritance_create_python_function({quote(self.class_id)}, __object_id, request, error)) begin",
            "      svx_payload_destroy(request);",
            "      svx_inheritance_registry::unbind(__object_id);",
            f'      $fatal(2, "SVX callback construction {self.class_id} failed: %s", error);',
            "    end",
            "    svx_payload_destroy(request);",
            "  endfunction",
            "  virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);",
            "    ok = 0; response = null;",
            '    error = {"callback-only adapter has no Python-to-SV methods: ", method_id};',
            "  endtask",
        ]
        for callback in self.callbacks:
            function = callback.timing == "function"
            lines.extend([
                f"  {'function void' if function else 'task'} {callback.name}();",
                "    bit ok; chandle request; chandle response; string error;",
                "    byte unsigned bytes[$];",
                '    request = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");',
            ])
            method_id = quote(f"{self.class_id}#{callback.name}")
            if function:
                lines.append(f"    response = svx_inheritance_call_python_function(__object_id, {method_id}, request, ok, error);")
            else:
                lines.append(f"    svx_inheritance_call_python(__object_id, {method_id}, request, ok, response, error);")
            lines.extend([
                "    svx_payload_destroy(request);",
                "    if (response != null) svx_payload_destroy(response);",
                f'    if (!ok) $fatal(2, "SVX callback {self.class_id}#{callback.name} failed: %s", error);',
                f"  {'endfunction' if function else 'endtask'}",
            ])
        return "\n".join([*lines, "endclass", ""])


_registered: dict[str, tuple[CallbackAdapter, type, type]] = {}

__all__ = ["Callback", "CallbackAdapter"]
