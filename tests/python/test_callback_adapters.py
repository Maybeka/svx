from __future__ import annotations

import json

import pytest

import svx
from svx import inheritance
from svx.callbacks import Callback, CallbackAdapter


def test_declarations_validate_before_generation():
    with pytest.raises(ValueError, match="timing"):
        Callback("run", "async")
    with pytest.raises(ValueError, match="unique"):
        CallbackAdapter("py://callback/Duplicate", (Callback("run", "task"),) * 2)
    with pytest.raises(ValueError, match="class ID"):
        CallbackAdapter('py://bad/"', ())
    with pytest.raises(ValueError, match="name"):
        Callback("svx_invoke", "task")


def test_render_is_deterministic_and_owns_private_plumbing():
    adapter = CallbackAdapter("py://callback/Render", (
        Callback("build", "function"), Callback("run", "task"),
    ))
    output = adapter.render_sv("RenderCallbacks")
    assert output == adapter.render_sv("RenderCallbacks")
    assert "function void build()" in output
    assert "task run()" in output
    assert "svx_inheritance_call_python_function" in output
    assert "svx_inheritance_call_python(__object_id" in output
    assert "svx_inheritance_registry::unbind(__object_id)" in output
    with pytest.raises(ValueError, match="name"):
        adapter.render_sv("bad;code")


def test_companion_binds_before_init_and_dispatches_original_instance(monkeypatch):
    instances = {}
    observed = []
    monkeypatch.setattr(inheritance, "bind_instance", lambda key, value: instances.__setitem__(key, value))
    monkeypatch.setattr(svx._native, "inheritance_get", instances.get)

    class Source:
        def __init__(self):
            assert instances[91] is self
            self.calls = 0

        def build(self):
            self.calls += 1
            observed.append(self)

    adapter = CallbackAdapter("py://callback/Source", (Callback("build", "function"),))
    before = dict(Source.__dict__)
    adapter.register_type(Source)
    adapter.register_type(Source)
    inheritance.create_python_instance(adapter.class_id, 91, b"")
    inheritance.dispatch_python_call(91, adapter.class_id + "#build", b"", True)
    assert type(instances[91]) is Source
    assert instances[91].calls == 1
    assert observed == [instances[91]]
    assert dict(Source.__dict__) == before


def test_constructor_failure_unbinds_original_receiver(monkeypatch):
    bound = []
    retired = []
    monkeypatch.setattr(inheritance, "bind_instance", lambda key, value: bound.append((key, value)))
    monkeypatch.setattr(inheritance, "unbind_instance", retired.append)

    class Failing:
        def __init__(self):
            raise ValueError("initialization failed")

    adapter = CallbackAdapter("py://callback/Failing", ())
    adapter.register_type(Failing)
    with pytest.raises(ValueError, match="initialization failed"):
        inheritance.create_python_instance(adapter.class_id, 92, b"")
    assert len(bound) == 1 and retired == [92]


def test_constructor_cannot_advance_time(monkeypatch):
    monkeypatch.setattr(inheritance, "bind_instance", lambda *_: None)
    monkeypatch.setattr(inheritance, "unbind_instance", lambda *_: None)

    class Blocking:
        def __init__(self):
            svx.delay(1, "ns")

    adapter = CallbackAdapter("py://callback/Blocking", ())
    adapter.register_type(Blocking)
    with pytest.raises(svx.SVXContextError, match="callback companion"):
        inheritance.create_python_instance(adapter.class_id, 93, b"")


def test_rejects_non_synchronous_or_non_instance_callbacks():
    class Async:
        async def run(self):
            pass

    class Static:
        @staticmethod
        def run():
            pass

    class Arguments:
        def run(self, arg):
            pass

    for source in (Async, Static, Arguments):
        adapter = CallbackAdapter(f"py://callback/{source.__name__}", (Callback("run", "task"),))
        with pytest.raises(TypeError):
            adapter.register_type(source)


def test_function_callback_cannot_wait(monkeypatch):
    class Waiting:
        def build(self):
            svx.delay(1, "ns")

    adapter = CallbackAdapter("py://callback/Waiting", (Callback("build", "function"),))
    adapter.register_type(Waiting)
    monkeypatch.setattr(svx._native, "inheritance_get", lambda _: Waiting())
    with pytest.raises(svx.SVXContextError, match="SV function callback"):
        inheritance.dispatch_python_call(94, adapter.class_id + "#build", b"", True)


def test_registration_can_restore_cleared_contracts(monkeypatch):
    class Source:
        def run(self):
            pass

    adapter = CallbackAdapter("py://callback/Restore", (Callback("run", "task"),))
    adapter.register_type(Source)
    monkeypatch.delitem(inheritance._constructor_contracts, adapter.class_id)
    monkeypatch.delitem(inheritance._method_contracts, adapter.class_id + "#run")
    monkeypatch.delitem(inheritance._python_subclasses, adapter.class_id)
    adapter.register_type(Source)
    assert adapter.class_id in inheritance._constructor_contracts
    assert adapter.class_id + "#run" in inheritance._method_contracts
    assert adapter.class_id in inheritance._python_subclasses


def test_runtime_selection_uses_existing_factory_and_original_receiver(monkeypatch):
    instances = {}
    calls = []
    monkeypatch.setattr(inheritance, "bind_instance", lambda key, value: instances.__setitem__(key, value))
    monkeypatch.setattr(svx._native, "inheritance_get", instances.get)

    class RuntimeSource:
        def __init__(self):
            assert instances[95] is self
            calls.append(self)

        def run(self):
            calls.append(self)

    adapter = CallbackAdapter("py://callback/RuntimeSelected", (Callback("run", "task"),))
    adapter.register_type(RuntimeSource)
    selector = "svx-callback-create:" + json.dumps({
        "class_id": adapter.class_id, "callbacks": [["run", "task"]],
    })
    inheritance.create_python_instance(selector, 95, b"")
    inheritance.dispatch_python_call(95, adapter.class_id + "#run", b"")
    assert type(instances[95]) is RuntimeSource
    assert calls == [instances[95], instances[95]]


@pytest.mark.parametrize("target,callbacks,match", [
    ("py://callback/Unknown", [["run", "task"]], "unregistered"),
    ("py://callback/SelectorShape", [["run", "function"]], "contract"),
])
def test_runtime_selection_rejects_incompatible_target_before_binding(monkeypatch, target, callbacks, match):
    class Source:
        def run(self):
            pass

    if target == "py://callback/SelectorShape":
        CallbackAdapter(target, (Callback("run", "task"),)).register_type(Source)
    monkeypatch.setattr(inheritance, "bind_instance", lambda *_: pytest.fail("must not bind"))
    selector = "svx-callback-create:" + json.dumps({"class_id": target, "callbacks": callbacks})
    with pytest.raises(svx.SVXInheritanceError, match=match):
        inheritance.create_python_instance(selector, 96, b"")
