import pytest
import svtypes

from svx import SVXInheritanceError
from svx import inheritance, runtime
from tests.integration.sv_field_mirror_schema import manifest_data


@pytest.fixture(autouse=True)
def codec_session(monkeypatch):
    monkeypatch.setattr(runtime, '_state', runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, '_codec_session', svtypes.CodecSession())


def test_call_contract_reregistration_after_real_codec_use_preserves_cache(monkeypatch):
    monkeypatch.setattr(inheritance, '_method_contracts', {})
    method = inheritance.parse_manifest(manifest_data()).classes[0].methods[1]
    contract = {method.canonical_id: inheritance._contract_data(method)}
    inheritance.register_contract(contract)
    monkeypatch.setattr(inheritance, 'call_sv', lambda *args: b'')
    assert inheritance.invoke_sv(71, method.canonical_id, {'value': 7}) is None
    cached = inheritance._method_contracts[method.canonical_id]
    request_schema = cached.request_schema
    assert request_schema is not None
    inheritance.register_contract(contract)
    assert inheritance._method_contracts[method.canonical_id] is cached
    assert cached.request_schema is request_schema
    changed = {method.canonical_id: {**contract[method.canonical_id], 'timing': 'task'}}
    with pytest.raises(SVXInheritanceError, match='conflicting SvTypes contract'):
        inheritance.register_contract(changed)
    assert inheritance._method_contracts[method.canonical_id] is cached


def test_constructor_reregistration_after_real_codec_use_preserves_cache(monkeypatch):
    monkeypatch.setattr(inheritance, '_constructor_contracts', {})
    class_id = 'sv://registration_cache/A'
    binding = inheritance.parse_manifest(manifest_data()).classes[0].fields[0].type_binding.runtime_spec()
    fields = (('seed', binding),)
    inheritance.register_constructor(class_id, fields)
    payload = inheritance.encode_constructor(class_id, {'seed': 7})
    assert inheritance._decode_constructor_arguments(class_id, payload) == (7,)
    cached = inheritance._constructor_contracts[class_id]
    schema = cached.request_schema
    assert schema is not None
    inheritance.register_constructor(class_id, fields)
    assert inheritance._constructor_contracts[class_id] is cached
    assert cached.request_schema is schema
    with pytest.raises(SVXInheritanceError, match='conflicting SvTypes constructor contract'):
        inheritance.register_constructor(class_id, ())
    assert inheritance._constructor_contracts[class_id] is cached
