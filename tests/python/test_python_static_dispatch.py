import sys
from types import ModuleType, SimpleNamespace

import pytest
from svtypes import CodecSession
import svx
import svx.inheritance as inheritance
from svx import runtime
from tests.integration.python_root_proxy_schema import ROOT_ID, manifest_data


@pytest.fixture
def generated_static(monkeypatch):
    calls = []

    class Source:
        wait_in_function = False

        def __init__(self, seed):
            raise AssertionError("static callback constructed a source instance")

        @staticmethod
        def scale(delta):
            if Source.wait_in_function:
                svx.delay(1, "ns")
            calls.append(("scale", delta))
            return delta * 3

        @staticmethod
        def wait_once():
            svx.delay(1, "ns")

        def ordinary(self):
            return 0

    module = ModuleType("static_root_source")
    module.Source = Source
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = manifest_data()
    source = data["classes"][0]
    source["symbol"] = module.__name__ + ".Source"
    source["fields"] = []
    source["methods"] = [method for method in source["methods"] if method.get("static")]
    model = inheritance.parse_manifest(data)
    for name in ("_constructor_contracts", "_method_contracts", "_python_subclasses", "_python_static_methods", "_python_static_sources"):
        monkeypatch.setattr(inheritance, name, {})
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", CodecSession())

    def unexpected_get(_object_id):
        raise AssertionError("static callback looked up a companion")

    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_get=unexpected_get))
    namespace = {"__name__": "generated_static_companion"}
    exec(inheritance._emit_python_root_companion(model, model.classes[0]), namespace)
    return model, Source, calls


def scale_request():
    method_id = ROOT_ID + "#scale"
    contract = inheritance._method_contracts[method_id]
    schema = inheritance._contract_schema(contract, method_id, "request")
    value = inheritance._record_value(schema, contract.request_fields, {"delta": 7})
    return inheritance._pack_call_record(schema, value)


def test_generated_static_function_uses_no_instance(generated_static):
    model, _, calls = generated_static
    method = model.classes[0].methods[0]
    response = inheritance.dispatch_python_call(
        0, inheritance._PYTHON_STATIC_METHOD_PREFIX + method.canonical_id,
        scale_request(), function_context=True,
    )
    contract = inheritance._method_contracts[method.canonical_id]
    schema = inheritance._contract_schema(contract, method.canonical_id, "response")
    result = inheritance._unpack_call_record(schema, response)
    assert inheritance._record_field(result, inheritance._method_return_slot(method)) == 21
    assert calls == [("scale", 7)]


def test_static_task_keeps_sync_blocking_context(generated_static, monkeypatch):
    waits = []
    monkeypatch.setattr(svx, "delay", lambda *args: waits.append(args))
    assert inheritance.dispatch_python_call(
        0, inheritance._PYTHON_STATIC_METHOD_PREFIX + ROOT_ID + "#wait_once", b"",
    ) == b""
    assert waits == [(1, "ns")]


def test_static_function_cannot_wait(generated_static):
    _, source, calls = generated_static
    source.wait_in_function = True
    with pytest.raises(svx.SVXContextError, match="function callback"):
        inheritance.dispatch_python_call(
            0, inheritance._PYTHON_STATIC_METHOD_PREFIX + ROOT_ID + "#scale",
            scale_request(), function_context=True,
        )
    assert calls == []


def test_static_callback_rejects_instance_id_and_missing_registration(generated_static, monkeypatch):
    method_id = inheritance._PYTHON_STATIC_METHOD_PREFIX + ROOT_ID + "#scale"
    request = scale_request()
    with pytest.raises(svx.SVXInheritanceError, match="must not use an instance ID"):
        inheritance.dispatch_python_call(91, method_id, request, function_context=True)
    monkeypatch.setattr(inheritance, "_python_static_methods", {})
    with pytest.raises(svx.SVXInheritanceError, match="no Python static source"):
        inheritance.dispatch_python_call(0, method_id, request, function_context=True)


def test_static_registration_rejects_nonstatic_and_foreign_owner_without_partial_write(generated_static):
    _, source, _ = generated_static
    before = inheritance._python_static_methods.copy()
    for invalid in (ROOT_ID + "#ordinary", "py://other/Source#scale"):
        with pytest.raises(svx.SVXInheritanceError):
            inheritance._register_python_static_methods(ROOT_ID, source, (ROOT_ID + "#scale", invalid))
        assert inheritance._python_static_methods == before


def test_static_registration_is_idempotent_and_rejects_other_source(generated_static):
    _, source, _ = generated_static
    method_id = ROOT_ID + "#scale"
    inheritance._register_python_static_methods(ROOT_ID, source, (method_id,))
    before = inheritance._python_static_methods.copy()

    class Other:
        @staticmethod
        def scale(delta):
            return delta

    with pytest.raises(svx.SVXInheritanceError, match="conflicting Python static source"):
        inheritance._register_python_static_methods(ROOT_ID, Other, (method_id,))
    assert inheritance._python_static_methods == before


def test_shutdown_clears_static_sources(generated_static):
    inheritance._register_python_static_source(ROOT_ID, 'static_root_source.Source', (ROOT_ID + '#scale',))
    assert inheritance._python_static_methods
    inheritance._shutdown_python_state()
    assert inheritance._python_static_methods == {}
    assert inheritance._python_static_sources == {}


def test_projected_static_source_resolves_declared_class_without_instance(generated_static, monkeypatch):
    _, source, calls = generated_static
    monkeypatch.setattr(inheritance, '_python_static_methods', {})
    inheritance._register_python_static_source(ROOT_ID, 'static_root_source.Source', (ROOT_ID + '#scale',))
    request = scale_request()
    response = inheritance.dispatch_python_call(
        0, inheritance._PYTHON_STATIC_METHOD_PREFIX + ROOT_ID + '#scale', request, function_context=True)
    assert response and calls == [('scale', 7)]
    assert inheritance._python_static_methods[ROOT_ID + '#scale'][0] is source
    with pytest.raises(svx.SVXInheritanceError, match='conflicting Python static source declaration'):
        inheritance._register_python_static_source(ROOT_ID, 'other.Source', (ROOT_ID + '#scale',))


def test_public_static_emission_registers_source_without_constructing(generated_static, monkeypatch):
    model, _, _ = generated_static
    sources = inheritance.emit_python_mirrors(model)
    source = next(text for path, text in sources.items() if path.name == 'static_root_source.py')
    namespace = {'__name__': 'public_static_companion'}
    exec(source, namespace)
    routes = []
    monkeypatch.setitem(namespace, 'invoke_sv_static',
                        lambda owner, method, values: routes.append((owner, method, values)) or 42)
    assert namespace['Source'].scale(14) == 42
    assert routes == [(ROOT_ID, ROOT_ID + '#scale', {'delta': 14})]
    response = inheritance.dispatch_python_call(
        0, inheritance._PYTHON_STATIC_METHOD_PREFIX + ROOT_ID + '#scale',
        scale_request(), function_context=True,
    )
    assert response
    assert '@staticmethod\n    def scale(delta):' in source
    assert 'invoke_sv_static(' in source
    sv = inheritance.emit_sv_mirrors(model)
    assert 'static function int scale(input int delta)' in sv
    assert 'svx_inheritance_call_python_function(0,' in sv
    assert 'register_static(' in sv
    assert 'virtual class SourceStaticGateway;' in sv
