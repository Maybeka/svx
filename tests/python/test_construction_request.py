import pytest
from svtypes import CodecSession

from svx import runtime
from svx.errors import SVXInheritanceError
from svx.inheritance import _pack_call_record, _record_value, _unpack_call_record
from tests.integration.construction_request_schema import request, values


@pytest.fixture(autouse=True)
def codec_session(monkeypatch):
    monkeypatch.setattr(runtime, '_state', runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, '_codec_session', CodecSession())


def test_heterogeneous_constructor_records_roundtrip_without_flattening():
    plan = request()
    arguments = values(plan)
    assert plan.decode(plan.encode(arguments)) == arguments
    assert len(plan.sv_record_types()) == 4
    assert all('class ' in record.to_sv_obj() for record in plan.sv_record_types())


@pytest.mark.parametrize('edit', ['missing', 'extra', 'wrong_fields', 'void_fields'])
def test_constructor_request_requires_exact_canonical_stages_and_fields(edit):
    plan = request()
    arguments = values(plan)
    keys = list(arguments)
    if edit == 'missing':
        del arguments[keys[0]]
    elif edit == 'extra':
        arguments['py://other/Unused'] = {}
    elif edit == 'wrong_fields':
        arguments[keys[2]] = {'seed': 29, 'label': 'wrong field'}
    else:
        arguments[keys[-1]] = {'seed': 3}
    with pytest.raises(TypeError):
        plan.encode(arguments)


@pytest.mark.parametrize('field,replacement', [
    ('target_id', 'sv://other/Target'),
    ('owner_1', 'sv://other/Child'),
    ('arguments_3', [1]),
])
def test_constructor_request_rejects_wrong_target_lineage_and_void_payload(field, replacement):
    plan = request()
    from svx.inheritance import _record_field
    decoded = _unpack_call_record(plan.schema, plan.encode(values(plan)))
    fields = {name: _record_field(decoded, name) for name, _ in plan.fields}
    fields[field] = replacement
    payload = _pack_call_record(plan.schema, _record_value(plan.schema, plan.fields, fields))
    with pytest.raises(SVXInheritanceError):
        plan.decode(payload)


def test_constructor_request_rejects_truncated_or_trailing_envelope():
    plan = request()
    payload = plan.encode(values(plan))
    for damaged in (payload[:-1], payload + b'\x00'):
        with pytest.raises(SVXInheritanceError):
            plan.decode(damaged)


def test_lineage_validation_precedes_any_inner_record_decode(monkeypatch):
    from svx import _construction
    from svx.inheritance import _record_field

    plan = request()
    decoded = _unpack_call_record(plan.schema, plan.encode(values(plan)))
    fields = {name: _record_field(decoded, name) for name, _ in plan.fields}
    fields['owner_3'] = fields['owner_0']
    fields['arguments_0'] = [255]
    payload = _pack_call_record(plan.schema, _record_value(plan.schema, plan.fields, fields))
    original = _construction._unpack_call_record
    schemas = []

    def unpack(schema, data):
        schemas.append(schema)
        return original(schema, data)

    monkeypatch.setattr(_construction, '_unpack_call_record', unpack)
    with pytest.raises(SVXInheritanceError, match='lineage differs'):
        plan.decode(payload)
    assert schemas == [plan.schema]


@pytest.mark.parametrize('payload', [[], [255]])
def test_constructor_request_rejects_damaged_inner_record(payload):
    from svx.inheritance import _record_field

    plan = request()
    decoded = _unpack_call_record(plan.schema, plan.encode(values(plan)))
    fields = {name: _record_field(decoded, name) for name, _ in plan.fields}
    fields['arguments_2'] = payload
    encoded = _pack_call_record(plan.schema, _record_value(plan.schema, plan.fields, fields))
    with pytest.raises(SVXInheritanceError, match='invalid construction request'):
        plan.decode(encoded)
