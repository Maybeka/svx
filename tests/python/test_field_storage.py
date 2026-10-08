import pytest

from svtypes import CodecSession, ExternalStorageError, Int, Queue, SvObject, svobj

from svx import SVXInheritanceError
from svx.declarations import SVMirror
from svx.field_storage import (
    FieldStorageKey,
    SVXFieldStorage,
    _field_operation_wire,
    bind_projected_fields,
    projected_field_identities,
)


@pytest.mark.parametrize('object_id', [True, False, 0, -1, 1 << 64, 1.5, '91'])
def test_field_and_mirror_bindings_reject_invalid_object_ids(object_id):
    with pytest.raises(ValueError, match='64-bit'):
        FieldStorageKey(object_id, 'py://checks/B.count')
    owner = SVMirror()
    with pytest.raises(ValueError, match='64-bit'):
        owner._svx_bind_remote_object(object_id)
    assert owner._svx_remote_object_id is None
    owner._svx_release_projected_fields()


def test_field_and_mirror_bindings_accept_largest_object_id():
    object_id = (1 << 64) - 1
    assert FieldStorageKey(object_id, 'py://checks/B.count').object_id == object_id
    owner = SVMirror()
    owner._svx_bind_remote_object(object_id)
    assert owner._svx_remote_object_id == object_id
    owner._svx_release_projected_fields()


@pytest.mark.parametrize('index', ['true', '-1', str(1 << 64), '1.5', '"1"'])
def test_field_operation_rejects_unrepresentable_index(index):
    with pytest.raises(SVXInheritanceError, match='index path segment'):
        _field_operation_wire('[{"kind":"index","index":' + index + '}]', 'read', None)


def test_field_operation_accepts_largest_wire_index():
    import struct

    envelope = _field_operation_wire(
        '[{"kind":"index","index":18446744073709551615}]', 'read', None,
    )
    assert envelope[15:23] == struct.pack('<Q', (1 << 64) - 1)


def test_retained_nested_field_view_closes_without_transport_or_local_fallback():
    @svobj
    class NestedOwner(SvObject):
        history = Queue[Queue[Int]]()
        local = Int()

    owner = NestedOwner()
    transport = RecordingTransport()
    field_id = 'py://checks/B.history'
    transport.values[field_id] = Int().pack(3)
    storage = SVXFieldStorage(transport)
    bind_projected_fields(
        owner, 91, projected_field_identities(owner, {'history': field_id}), storage=storage,
    )
    retained = owner.history[0][1]
    assert retained.value == 3
    retained.value = 9
    expected_path = '[{"kind":"index","index":0},{"kind":"index","index":1}]'
    assert transport.reads[-1][3] == expected_path
    assert transport.writes[-1][3:5] == (expected_path, 'set')
    calls = (len(transport.reads), len(transport.writes))
    storage.close()
    with pytest.raises(ExternalStorageError) as error:
        _ = retained.value
    assert 'closed' in str(error.value.__cause__)
    with pytest.raises(ExternalStorageError):
        retained.value = 4
    assert calls == (len(transport.reads), len(transport.writes))
    owner.local.value = 7
    assert owner.local.value == 7


def test_nested_field_codegen_uses_public_typedef_context():
    from svx.inheritance import emit_sv_mirrors, parse_manifest
    from tests.integration.sv_field_mirror_schema import manifest_data

    text = emit_sv_mirrors(parse_manifest(manifest_data(include_nested_fields=True)))
    assert 'typedef int __svx_field_nested_values_0_t [$];' in text
    assert 'queue_packer#(__svx_field_nested_values_0_t,' in text
    assert '__svx_field_nested_values_0_t field_value;' in text
    assert 'int [$] field_value;' not in text
    assert 'this.nested_values[operation.path_index[0]][operation.path_index[1]]' in text
    assert 'operation.path_index[1] < this.nested_values[operation.path_index[0]].size()' in text


def test_deep_field_codegen_resolves_member_key_and_index_with_public_descriptors():
    import svtypes
    from svx.inheritance import _emit_sv_deep_field_access

    @svtypes.svobj
    class DeepPathOwner(svtypes.SvObject):
        rows = svtypes.AssocArray[svtypes.String, svtypes.Queue[svtypes.Int]]()

    text = '\n'.join(_emit_sv_deep_field_access(DeepPathOwner(), 'this.record', 'sv://test/Owner.record'))
    assert 'operation.path_member[0] == "rows"' in text
    assert 'this.record != null' in text
    assert 'operation.path_kind[1] == 3' in text
    assert 'this.record.rows.exists(field_key_1)' in text
    assert 'operation.path_index[2] < this.record.rows[field_key_1].size()' in text
    assert 'this.record.rows[field_key_1][operation.path_index[2]]' in text
    assert 'this.record.rows[field_key_1].push_back(field_element)' in text
    assert 'this.record.rows.delete(field_key_1)' in text


@pytest.mark.parametrize('sequence', ['Queue', 'DynArray'])
def test_deep_sequence_mutation_uses_target_lvalue_and_svtypes_length_codec(sequence):
    import svtypes
    from svx.inheritance import _emit_sv_deep_field_access

    annotation = getattr(svtypes, sequence)[getattr(svtypes, sequence)[svtypes.Int]]
    with svtypes.sv_codegen_context(annotation()):
        text = '\n'.join(_emit_sv_deep_field_access(annotation(), 'this.matrix', 'sv://test/Owner.matrix'))
    assert 'operation.path_kind.size() == 2' in text
    assert 'operation.path_index[1] <= this.matrix[operation.path_index[0]].size()' in text
    assert 'field_length < 0' in text
    assert f'{svtypes.sv_packer_expression(svtypes.Int())}::unpack(field_length' in text
    if sequence == 'Queue':
        assert 'this.matrix[operation.path_index[0]].push_back(field_default)' in text
    else:
        assert 'this.matrix[operation.path_index[0]] = new[field_length](this.matrix[operation.path_index[0]])' in text


def test_field_codegen_rejects_missing_public_render_context(monkeypatch):
    import svtypes
    from svx.inheritance import emit_sv_mirrors, parse_manifest
    from tests.integration.sv_field_mirror_schema import manifest_data

    manifest = parse_manifest(manifest_data())
    monkeypatch.setattr(svtypes, 'sv_codegen_context', None)
    with pytest.raises(SVXInheritanceError, match='public SvTypes sv_codegen_context'):
        emit_sv_mirrors(manifest)


def test_field_path_overflow_rejected_before_transport():
    owner = FieldOwner()
    transport = RecordingTransport()
    bind_projected_fields(
        owner, 91, projected_field_identities(owner, {'history': 'py://checks/B.history'}),
        storage=SVXFieldStorage(transport),
    )
    retained = owner.history[1 << 64]
    with pytest.raises(ExternalStorageError) as error:
        _ = retained.value
    assert 'index path segment' in str(error.value.__cause__)
    with pytest.raises(ExternalStorageError):
        retained.value = 1
    assert transport.reads == [] and transport.writes == []


@svobj
class FieldOwner(SvObject):
    count = Int()
    local = Int()
    history = Queue[Int]()


class RecordingTransport:
    def __init__(self) -> None:
        self.values = {"py://checks/B.count": Int().pack(3)}
        self.reads = []
        self.writes = []

    def read_field(self, object_id, field_id, descriptor, path):
        self.reads.append((object_id, field_id, descriptor, path))
        return self.values[field_id]

    def write_field(self, object_id, field_id, descriptor, path, operation, payload):
        self.writes.append((object_id, field_id, descriptor, path, operation, payload))
        self.values[field_id] = payload
        return None


def test_selected_svtypes_fields_bind_to_svx_object_storage():
    owner = FieldOwner()
    transport = RecordingTransport()
    ids = projected_field_identities(owner, {"count": "py://checks/B.count"})
    storage = SVXFieldStorage(transport)
    bind_projected_fields(owner, 91, ids, storage=storage)

    assert owner.count.value == 3
    owner.count.value = 9
    assert owner.count.value == 9
    assert transport.reads[0][0:2] == (91, "py://checks/B.count")
    assert transport.reads[0][3] == "[]"
    assert transport.writes[-1][0:2] == (91, "py://checks/B.count")
    assert transport.writes[-1][4] == "set"
    # An omitted field remains a normal owner-local SvTypes value.
    owner.local.value = 4
    assert owner.local.value == 4


def test_projected_field_identity_rejects_unknown_or_shadowed_names():
    owner = FieldOwner()
    with pytest.raises(SVXInheritanceError, match="no unique declaring class"):
        projected_field_identities(owner, {"missing": "py://checks/B.missing"})


def test_projected_value_field_is_not_confused_with_svtypes_base_property():
    @svobj
    class ValueOwner(SvObject):
        value = Int()

    owner = ValueOwner()
    identities = projected_field_identities(owner, {'value': 'sv://fields/ValueOwner.value'})
    assert len(identities) == 1
    identity = next(iter(identities))
    assert identity.declaring_type is ValueOwner and identity.name == 'value'


def test_projected_queue_keeps_svtypes_local_operation_paths():
    owner = FieldOwner()
    transport = RecordingTransport()
    ids = projected_field_identities(owner, {"history": "py://checks/B.history"})
    bind_projected_fields(owner, 91, ids, storage=SVXFieldStorage(transport))

    owner.history.value.append(3)
    owner.history.value.insert(0, 2)
    owner.history.value[0] = 4

    assert [(write[3], write[4]) for write in transport.writes] == [
        ("[]", "append"),
        ('[{"kind":"index","index":0}]', "insert"),
        ('[{"kind":"index","index":0}]', "set"),
    ]


def test_repeated_projection_binding_reuses_receiver_storage():
    @svobj
    class ReboundMirrorOwner(SVMirror):
        count = Int()
        local = Int()

    owner = ReboundMirrorOwner()
    owner._svx_bind_remote_object(91)
    owner._svx_field_storage = SVXFieldStorage(RecordingTransport())
    storage = owner._svx_field_storage
    owner._svx_bind_projected_fields({"count": "py://checks/B.count"})
    retained = owner.count
    owner.local.value = 7
    owner._svx_bind_projected_fields({"count": "py://checks/B.count"})
    assert owner._svx_field_storage is storage
    assert retained.value == 3
    assert owner.local.value == 7


def test_released_mirror_fields_never_fall_back_to_local_storage():
    @svobj
    class MirrorOwner(SVMirror):
        count = Int()
        local = Int()

    owner = MirrorOwner()
    owner._svx_bind_remote_object(91)
    owner._svx_field_storage = bind_projected_fields(
        owner, 91, projected_field_identities(owner, {"count": "py://checks/B.count"}),
        storage=SVXFieldStorage(RecordingTransport()),
    )
    retained = owner.count
    assert retained.value == 3
    owner.local.value = 7
    owner._svx_release_projected_fields()
    owner._svx_release_projected_fields()
    for value in (retained, owner.count):
        with pytest.raises(ExternalStorageError) as error:
            _ = value.value
        assert "closed" in str(error.value.__cause__)
        with pytest.raises(ExternalStorageError):
            value.value = 4
    assert owner.local.value == 7


def test_mirror_release_removes_only_its_codec_identity():
    import gc
    import weakref

    session = CodecSession()
    owner = SVMirror(session=session)
    sibling = SVMirror(session=session)
    number = owner.svtypes_object_number
    sibling_number = sibling.svtypes_object_number
    assert session.get(number) is owner
    reference = weakref.ref(owner)

    owner._svx_release_projected_fields()
    owner._svx_release_projected_fields()
    assert session.get(number) is None
    assert session.get(sibling_number) is sibling
    del owner
    gc.collect()
    assert reference() is None
    session.close()


def test_mirror_release_before_svtypes_initialization_is_safe():
    owner = SVMirror.__new__(SVMirror)
    owner._svx_release_projected_fields()


def test_mirror_release_preserves_foreign_codec_registration():
    session = CodecSession()
    owner = SVMirror(session=session)
    number = owner.svtypes_object_number
    session.remove(number)
    replacement = SvObject(session=session, svtypes_object_number=number)
    owner._svx_release_projected_fields()
    assert session.get(number) is replacement
    session.close()
