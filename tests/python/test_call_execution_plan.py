from types import SimpleNamespace

import pytest
import svtypes
import svx
from svx import inheritance as bridge, runtime


def spec(annotation):
    codec = svtypes.materialize_type_spec(annotation, location='test call plan')
    return {'svtypes': svtypes.type_spec_identity(annotation),
            'unified_type_name': svtypes.unified_type_name(codec),
            'encoding_descriptor': svtypes.encoding_descriptor(codec).to_dict()}


@pytest.fixture(autouse=True)
def session(monkeypatch):
    monkeypatch.setattr(runtime, '_state', runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, '_codec_session', svtypes.CodecSession())


def test_prepared_records_do_not_reinspect_or_rematerialize_types(monkeypatch):
    fields = (('value', spec(svtypes.Int)), ('items', spec(svtypes.DynArray[svtypes.Int])))
    schema = bridge._call_record_schema('sv://plans/Source#call', 'request', fields)
    assert not schema.validators

    def forbidden(*args, **kwargs):
        pytest.fail('prepared record repeated static discovery')

    monkeypatch.setattr(bridge.inspect, 'signature', forbidden)
    monkeypatch.setattr(bridge, '_svtypes_codec', forbidden)
    monkeypatch.setattr(bridge, '_remote_ref_validator', forbidden)
    for _ in range(3):
        value = bridge._record_value(schema, fields, {'value': 7, 'items': [1, 2]})
        payload = bridge._pack_call_record(schema, value)
        result = bridge._unpack_call_record(schema, payload)
        bridge._validate_record_fields(result, fields, schema=schema)
        assert bridge._record_field(result, 'value') == 7
        assert list(bridge._record_field(result, 'items')) == [1, 2]


def test_prepared_references_still_check_live_receiver_each_time(monkeypatch):
    target = 'sv://plans/Target'
    fields = (('item', spec(svtypes.RemoteRef[target])),)
    schema = bridge._call_record_schema('sv://plans/Source#ref', 'request', fields)
    live = {7: SimpleNamespace(__svx_foreign_class_id__=target)}
    monkeypatch.setattr(svx, '_native', SimpleNamespace(inheritance_get=live.get))
    bridge._record_value(schema, fields, {'item': 7})
    del live[7]
    with pytest.raises(svx.SVXInheritanceError, match='stale'):
        bridge._record_value(schema, fields, {'item': 7})
    live[7] = SimpleNamespace(__svx_foreign_class_id__='sv://plans/Other')
    with pytest.raises(svx.SVXInheritanceError, match='type mismatch'):
        bridge._record_value(schema, fields, {'item': 7})


def test_prepared_records_keep_payload_and_argument_errors():
    fields = (('value', spec(svtypes.Int)),)
    schema = bridge._call_record_schema('sv://plans/Source#call', 'request', fields)
    with pytest.raises(TypeError, match='missing value'):
        bridge._record_value(schema, fields, {})
    value = bridge._record_value(schema, fields, {'value': 4})
    payload = bridge._pack_call_record(schema, value)
    with pytest.raises(svx.SVXInheritanceError, match='trailing bytes'):
        bridge._unpack_call_record(schema, payload + b'\0')
    with pytest.raises(ValueError, match='Not enough bytes'):
        bridge._unpack_call_record(schema, payload[:-1])


@pytest.mark.parametrize('contextual', [True, False])
def test_schema_adapter_prepares_legacy_and_context_interfaces(contextual):
    calls = []
    class Value:
        pass
    class Legacy:
        value_type = Value
        def pack(self, value):
            calls.append('pack')
            return b''
        def unpack(self, payload):
            calls.append('unpack')
            return Value(), 0
    class Contextual:
        value_type = Value
        def pack(self, value, context):
            calls.append(context)
            return b''
        def unpack(self, payload, context):
            calls.append(context)
            return Value(), 0
    schema = bridge._PreparedCallSchema((Contextual if contextual else Legacy)(), Value, (), ())
    assert bridge._pack_call_record(schema, Value()) == b''
    assert isinstance(bridge._unpack_call_record(schema, b''), Value)
    assert len(calls) == 2
    if contextual:
        assert isinstance(calls[0], svtypes.PackContext)
        assert isinstance(calls[1], svtypes.UnpackContext)
    else:
        assert calls == ['pack', 'unpack']
