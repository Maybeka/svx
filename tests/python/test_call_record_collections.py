import pytest
import svtypes

from svx.declarations import _svtypes_binding
from svx.inheritance import (
    _call_record_schema, _record_field, _record_value, _sv_record_type, _type_binding,
)


class TransportMode(svtypes.Enum[svtypes.Bit[2]]):
    IDLE = 0
    ACTIVE = 2


@pytest.mark.parametrize('annotation,values', [
    (svtypes.Array[svtypes.Int, 2], [3, 5]),
    (svtypes.DynArray[svtypes.Int], [3, 5]),
    (svtypes.Queue[svtypes.Int], [3, 5]),
    (svtypes.AssocArray[svtypes.String, svtypes.Int], {'first': 3, 'second': 5}),
])
def test_collection_descriptors_are_values_and_transport_coverage_preserves_wire(annotation, values, monkeypatch):
    import svx.runtime as runtime
    session = svtypes.CodecSession()
    monkeypatch.setattr(runtime, 'codec_session', lambda: session)
    spec = _svtypes_binding(annotation, where='collection test')
    binding = _type_binding(spec, 'collection test', allow_void=False)
    fields = (('value', spec),)
    owner = 'sv://collection_test/Driver#exchange'
    schema = _call_record_schema(owner, 'request', fields)
    source = annotation()
    source.value = values
    original_cov = source.cov
    result = _record_value(schema, fields, {'value': source})
    assert _record_field(result, 'value') == values
    assert source.value == values
    generated = _sv_record_type(owner, 'request', (('value', binding),))
    assert svtypes.encoding_descriptor(generated).to_dict() == svtypes.encoding_descriptor(schema.value_type).to_dict()
    assert 'covergroup' not in generated.to_sv_obj()
    assert source.cov == original_cov


def test_enum_transport_extras_do_not_change_schema_or_user_options(monkeypatch):
    import svx.runtime as runtime
    session = svtypes.CodecSession()
    monkeypatch.setattr(runtime, 'codec_session', lambda: session)
    source = TransportMode(cov=True, plusarg=True)
    source.value = TransportMode.ACTIVE
    spec = _svtypes_binding(TransportMode, where='enum transport test')
    binding = _type_binding(spec, 'enum transport test', allow_void=False)
    owner = 'sv://enum_test/Driver#exchange'
    fields = (('value', spec),)
    runtime_schema = _call_record_schema(owner, 'request', fields)
    generated = _sv_record_type(owner, 'request', (('value', binding),))
    assert svtypes.encoding_descriptor(generated).to_dict() == svtypes.encoding_descriptor(runtime_schema.value_type).to_dict()
    text = generated.to_sv_obj()
    assert 'covergroup' not in text and '$value$plusargs' not in text
    assert source.cov is True and source.plusarg is True
    assert source.value == TransportMode.ACTIVE


@pytest.mark.parametrize('annotation', [svtypes.Array[svtypes.Int, 2], svtypes.DynArray[svtypes.Int],
                                       svtypes.Queue[svtypes.Int], svtypes.AssocArray[svtypes.String, svtypes.Int]])
def test_owner_record_collection_aliases_use_native_scope_and_restore_after_failure(annotation):
    from svx.inheritance import _sv_value_type
    from svx.owner_records import with_local_call_records
    binding = _type_binding(_svtypes_binding(annotation, where='owner collection'), 'owner collection', allow_void=False)
    qualified = _sv_value_type(binding)
    assert qualified.startswith('svx_call_records_pkg::')

    @with_local_call_records
    def local():
        assert _sv_value_type(binding) == qualified.removeprefix('svx_call_records_pkg::')
        raise RuntimeError('test scope cleanup')

    with pytest.raises(RuntimeError, match='test scope cleanup'):
        local()
    assert _sv_value_type(binding) == qualified
