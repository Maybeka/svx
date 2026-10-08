import pytest

import svx
from svx import SVXContextError, SVXInheritanceError
from svx import _native
from svx.callback_context import (
    blocking_operations_disallowed,
    require_blocking_operations_allowed,
)
from svx.inheritance import dispatch_python_call, register_contract
from svx.declarations import _vif_operations
from svx.sv_scan import SVVirtualInterfaceFact


def test_function_callback_guard_is_automatic_and_restored(monkeypatch):
    class Callback:
        def wait(self):
            svx.delay(1, "ns")

    register_contract({"py://function_probe/Callback#wait": {
        "timing": "function", "parameters": (), "request": (), "response": (),
    }})
    monkeypatch.setattr(_native, "inheritance_get", lambda _: Callback())
    with pytest.raises(SVXContextError, match="SV function callback"):
        dispatch_python_call(1, "py://function_probe/Callback#wait", b"", True)
    require_blocking_operations_allowed("after callback")


def test_nested_function_guard_restores_outer_restriction():
    with blocking_operations_disallowed("outer function"):
        with blocking_operations_disallowed("inner function"):
            with pytest.raises(SVXContextError, match="inner function"):
                require_blocking_operations_allowed("wait")
        with pytest.raises(SVXContextError, match="outer function"):
            require_blocking_operations_allowed("wait")
    require_blocking_operations_allowed("wait")


def test_function_callback_cannot_invoke_an_sv_task():
    from svx.inheritance import call_sv

    with blocking_operations_disallowed("function callback"):
        with pytest.raises(SVXContextError, match="SV task"):
            call_sv(1, "sv://probe/Item#wait")


def test_unknown_modport_is_rejected_before_generating_a_view():
    fact = SVVirtualInterfaceFact("bus_if", frozenset({"master"}))
    with pytest.raises(SVXInheritanceError, match="no modport missing"):
        _vif_operations("sv-vif://bus_if/missing", fact, "missing")
