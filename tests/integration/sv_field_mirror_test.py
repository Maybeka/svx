import svx
import os
import json
from pathlib import PurePosixPath
from svtypes import ExternalStorageError, Int
from svx import _native
from svx.inheritance import emit_python_mirrors, encode_constructor, invoke_sv, parse_manifest
from svx_mirror.field_owner_pkg import Base


class Derived(Base):
    local_count: Int = Int()


@svx.export(name="sv_field_mirror.run")
def run():
    import gc
    import weakref

    value = Derived()
    session, number = value.codec_session, value.svtypes_object_number
    assert session.get(number) is value
    reference = weakref.ref(value)
    assert value.get_count() == 11
    assert value.count.value == 11, "mirror field shadows the real SV base field"
    value.count.value = 19
    assert value.get_count() == 19, "Python field assignment did not update the SV base"
    value.set_count(23)
    assert value.count.value == 23, "SV method assignment is not visible through the mirror"
    for initial, name in enumerate(('bytes', 'field_offset', 'field_value', 'error', 'ok', 'response'), 5):
        field = getattr(value, name)
        assert field.value == initial, name
        field.value = initial + 100
        assert field.value == initial + 100, name
    assert list(value.operation.value) == [2, 3]
    value.operation[0].value = 4
    value.operation.value.insert(1, 5)
    value.operation.value.append(6)
    del value.operation.value[2]
    assert list(value.operation.value) == [4, 5, 6]
    svx.display('SVX_FIELD_MEMBER_NAMES_PASS')
    assert list(value.fixed_values.value) == [12, 13, 14]
    value.fixed_values[1].value = 27
    assert list(value.fixed_values.value) == [12, 27, 14]
    value.fixed_values.value = [31, 32, 33]
    assert value.fixed_values[2].value == 33
    svx.display('SVX_FIXED_ARRAY_FIELD_PASS')
    if os.environ.get('SVX_NESTED_FIELD_AUDIT') == '1':
        from svtypes import Queue
        expected = Queue[Queue[Int]]()
        expected.value = [[1, 2], [3, 4]]
        def snapshot():
            return _native.inheritance_call_sv(
                value._svx_remote_object_id,
                'sv://field_owner_pkg/Base.nested_values@svx_field_read', b'', function=True,
            )
        assert snapshot() == expected.pack(expected.value)
        retained_slices = []
        for selection, position in ((slice(None), 0), (slice(None, None, -1), 1)):
            rows = value.nested_values.value[selection]
            assert isinstance(rows, list)
            row = rows[0]
            original = row[0]
            row[0] = 73
            assert value.nested_values[position][0].value == 73
            assert value.nested_values[1 - position][0].value == (3 if position == 0 else 1)
            row[0] = original
            retained_slices.append(row)
        assert snapshot() == expected.pack(expected.value)
        value.nested_values.value = [[5, 6], [3, 4]]
        expected.value = [[5, 6], [3, 4]]
        assert snapshot() == expected.pack(expected.value)
        value.nested_values[0].value = [8, 9]
        expected.value = [[8, 9], [3, 4]]
        before = snapshot()
        assert before == expected.pack(expected.value)
        endpoints = []
        original_call = _native.inheritance_call_sv
        def track_local_call(object_id, method_id, *args, **kwargs):
            endpoints.append(method_id)
            return original_call(object_id, method_id, *args, **kwargs)
        _native.inheritance_call_sv = track_local_call
        try:
            assert value.nested_values[0][1].value == 9
            value.nested_values[0][1].value = 99
        finally:
            _native.inheritance_call_sv = original_call
        assert endpoints == ['sv://field_owner_pkg/Base.nested_values@svx_field_operation'] * 2
        expected.value = [[8, 99], [3, 4]]
        assert snapshot() == expected.pack(expected.value)
        for write in (False, True):
            try:
                if write:
                    value.nested_values[0][9].value = 55
                else:
                    _ = value.nested_values[0][9].value
            except ExternalStorageError:
                pass
            else:
                raise AssertionError('out-of-range nested path silently succeeded')
            assert snapshot() == expected.pack(expected.value)
        svx.display('SVX_NESTED_FIELD_LOCAL_ACCESS_PASS')
        _check_deep_container_mutation(value)
    retained_count = value.count
    value.local_count.value = 7
    svx.close_instance(value)
    svx.close_instance(value)
    if os.environ.get('SVX_NESTED_FIELD_AUDIT') == '1':
        for row in retained_slices:
            try:
                row[0] = 74
            except ExternalStorageError:
                pass
            else:
                raise AssertionError('slice child retained active projected storage after close')
        svx.display('SVX_NESTED_SLICE_BINDING_PASS')
    assert session.get(number) is None, 'closed mirror remains in codec registry'
    assert value.local_count.value == 7
    try:
        _ = retained_count.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("object close revived projected field storage")
    del retained_count, field, value
    gc.collect()
    assert reference() is None, 'closed mirror retained after native release'
    svx.display("SVX_SV_FIELD_MIRROR_PASS")

    retained = []
    failed_identities = []
    original = ValueError("generated mirror initialization failed")

    class FailedDerived(Derived):
        def __init__(self):
            super().__init__()
            self.count.value = 37
            retained.append(self.count)
            failed_identities.append((self.codec_session, self.svtypes_object_number))
            raise original

        def _svx_release_projected_fields(self):
            super()._svx_release_projected_fields()
            raise RuntimeError("generated mirror cleanup failed after close")

    class_id = "sv://field_owner_pkg/Base"
    object_id = _native.inheritance_create_sv(class_id, encode_constructor(class_id, {}))
    policy = svx.get_exception_policy()
    svx.set_exception_policy(svx.REPORT)
    try:
        try:
            FailedDerived.__svx_create_from_sv__(object_id)
        except ValueError as error:
            assert error is original
            assert any("close projected storage" in note for note in error.__notes__)
            assert any("unbind Python companion" in note for note in error.__notes__)
        else:
            raise AssertionError("generated mirror lost its initializer exception")
    finally:
        svx.set_exception_policy(policy)
    assert _native.inheritance_get(object_id) is None
    assert all(session.get(number) is None for session, number in failed_identities)
    try:
        _ = retained[0].value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("failed generated mirror storage remained active")
    svx.close_instance(object_id)
    svx.display("SVX_SV_FIELD_MIRROR_INIT_FAILURE_PASS")
    _check_existing_field_view()
    _prepare_shutdown_identity_check()


def _check_deep_container_mutation(value):
    from svtypes import DynArray, FieldDescriptor, FieldOperation, FieldPath, Queue
    from svx.field_storage import FieldStorageKey

    assert value.fixed_matrix[0][1].value == 12
    value.fixed_matrix[0][1].value = 21
    assert value.fixed_matrix[0][1].value == 21
    assert list(value.fixed_matrix[1].value) == [13, 14]
    value.fixed_matrix[1].value = [31, 32]
    assert list(value.fixed_matrix[0].value) == [11, 21]
    for indices in ((0, 2), (2, 0)):
        try:
            value.fixed_matrix[indices[0]][indices[1]].value = 99
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('fixed matrix out-of-range write unexpectedly accepted')
    assert list(value.fixed_matrix[0].value) == [11, 21]
    assert list(value.fixed_matrix[1].value) == [31, 32]
    value.fixed_matrix[0].value[::-1] = [41, 42]
    assert list(value.fixed_matrix[0].value) == [42, 41]
    assert list(value.fixed_matrix[1].value) == [31, 32]
    svx.display('SVX_DEEP_FIXED_ARRAY_PASS')

    def resize(name, codec, path, length):
        value._svx_field_storage.write(
            FieldStorageKey(value._svx_remote_object_id, f'sv://field_owner_pkg/Base.{name}'),
            FieldDescriptor(codec), path, FieldOperation.RESIZE, Int().pack(length))

    for name, codec in (
        ('nested_values', Queue[Queue[Int]]()),
        ('nested_dynamic', DynArray[DynArray[Int]]()),
    ):
        field = getattr(value, name)
        field.value = [[1, 2, 3, 4, 5], [7, 8]]
        writes = []
        transport = value._svx_field_storage._transport
        original_write = transport.write_field

        def record_write(*args, **kwargs):
            writes.append((args[3], args[4]))
            return original_write(*args, **kwargs)

        transport.write_field = record_write
        try:
            field[0].value[1:3] = [21, 22, 23]
        finally:
            transport.write_field = original_write
        assert list(field[0].value) == [1, 21, 22, 23, 4, 5]
        assert len(writes) == 3
        assert [operation for _, operation in writes] == ['set', 'set', 'insert']
        assert [tuple(segment['index'] for segment in json.loads(path))
                for path, _ in writes] == [(0, 1), (0, 2), (0, 3)]
        field[0].value[1:4] = [31]
        assert list(field[0].value) == [1, 31, 4, 5]
        field[0].value[::-2] = [51, 41]
        assert list(field[0].value) == [1, 41, 4, 51]
        del field[0].value[::2]
        assert list(field[0].value) == [41, 51]
        assert list(field[1].value) == [7, 8]
        field.value = [[1, 2], [3, 4]]
        field[0].value.append(5)
        field[0].value.insert(1, 6)
        assert list(field[0].value) == [1, 6, 2, 5]
        field[0].value.insert(4, 7)
        assert field[0].value.pop() == 7
        assert field[0].value.pop(2) == 2
        del field[0].value[0]
        assert list(field[0].value) == [6, 5]
        resize(name, codec, FieldPath().index(0), 4)
        assert list(field[0].value) == [6, 5, 0, 0]
        resize(name, codec, FieldPath().index(0), 1)
        assert list(field[0].value) == [6]
        assert list(field[1].value) == [3, 4]
        resize(name, codec, FieldPath(), 1)
        assert list(field[0].value) == [6] and len(field.value) == 1
        resize(name, codec, FieldPath().index(0), 0)
        field[0].value.insert(0, 9)
        assert list(field[0].value) == [9]
        try:
            resize(name, codec, FieldPath().index(0), -1)
        except RuntimeError as error:
            assert 'nonnegative length' in str(error)
        else:
            raise AssertionError('negative resize unexpectedly accepted')
        assert list(field[0].value) == [9]
    assert value.keyed_values['left'][1].value == 6
    value.keyed_values['left'][1].value = 19
    value.keyed_values['left'].value.append(20)
    value.keyed_values['left'].value.insert(1, 21)
    assert value.keyed_values['left'].value.pop(0) == 5
    assert list(value.keyed_values['left'].value) == [21, 19, 20]
    assert list(value.keyed_values['right'].value) == [7, 8]
    value.keyed_values.value['new'] = [31, 32]
    assert value.keyed_values['new'][0].value == 31
    del value.keyed_values.value['new']
    record = value.record.value
    assert record.rows['left'][1].value == 42
    record.rows['left'][1].value = 51
    record.rows['left'].value.append(52)
    record.rows['left'].value.insert(1, 53)
    assert record.rows['left'].value.pop(0) == 41
    assert list(record.rows['left'].value) == [53, 51, 52]
    assert list(record.rows['right'].value) == [43, 44]
    record.rows.value['new'] = [61, 62]
    assert record.rows['new'][1].value == 62
    del record.rows.value['new']
    try:
        _ = record.rows['missing'][0].value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('missing associative key unexpectedly accepted')
    record.svtypes_auto_cov.sample()
    coverage = record.svtypes_auto_cov.instance.snapshot()['rows']
    assert coverage['samples'] == 5
    assert sum(coverage['hits'].values()) == 5
    record.rows['left'][0].value = 54
    record.svtypes_auto_cov.sample()
    assert record.svtypes_auto_cov.instance.snapshot()['rows']['samples'] == 10
    svx.display('SVX_PROJECTED_NESTED_COVERAGE_PASS')
    grid = record.svtypes_auto_cov.instance.snapshot()
    for i in range(2):
        for j in range(2):
            assert grid[f'grid[{i}][{j}]']['hits'] == {'auto[0]': 2}
    record.grid[0][0].value = 1
    record.svtypes_auto_cov.sample()
    grid = record.svtypes_auto_cov.instance.snapshot()
    assert grid['grid[0][0]']['hits'] == {'auto[0]': 2, 'auto[1]': 1}
    assert grid['grid[1][1]']['hits'] == {'auto[0]': 3}
    svx.display('SVX_PROJECTED_FIXED_MATRIX_COVERAGE_PASS')
    record.lanes.value = [[0, 1], []]
    record.svtypes_auto_cov.sample()
    lanes = record.svtypes_auto_cov.instance.snapshot()
    assert lanes['lanes[0]']['hits'] == {'auto[0]': 1, 'auto[1]': 1}
    assert lanes['lanes[1]']['samples'] == 0
    record.lanes[1].value.append(1)
    record.svtypes_auto_cov.sample()
    lanes = record.svtypes_auto_cov.instance.snapshot()
    assert lanes['lanes[0]']['hits'] == {'auto[0]': 2, 'auto[1]': 2}
    assert lanes['lanes[1]']['hits'] == {'auto[1]': 1}
    svx.display('SVX_PROJECTED_INDEXED_DYNAMIC_COVERAGE_PASS')
    del record
    svx.display('SVX_DEEP_CONTAINER_MUTATION_PASS')
    svx.display('SVX_DEEP_SLICE_PASS')


def _prepare_shutdown_identity_check():
    class ShutdownDerived(Derived):
        def _svx_release_projected_fields(self):
            session, number = self.codec_session, self.svtypes_object_number
            super()._svx_release_projected_fields()
            assert session.get(number) is None, 'shutdown retained mirror codec identity'
            print('SVX_MIRROR_SHUTDOWN_IDENTITY_PASS', flush=True)

    value = ShutdownDerived()
    assert value.codec_session.get(value.svtypes_object_number) is value


def _check_existing_field_view():
    from tests.integration.sv_field_mirror_schema import manifest_data
    data = manifest_data()
    data['classes'] = data['classes'][:1]
    del data['classes'][0]['constructor']
    text = emit_python_mirrors(parse_manifest(data))[
        PurePosixPath('svx_mirror/field_owner_pkg.py')]
    namespace = {'__name__': 'tests.generated_existing_field_mirror'}
    exec(compile(text, '<generated existing field mirror>', 'exec'), namespace)
    Existing = namespace['Base']
    class_id = 'sv://field_owner_pkg/Base'
    # The fixture's separately declared factory supplies an existing dispatchable
    # endpoint. The constructorless view must only wrap it, not invoke that factory.
    object_id = _native.inheritance_create_sv(class_id, encode_constructor(class_id, {}))
    value = Existing(object_id)
    assert value._svx_remote_object_id == object_id
    assert value.count.value == value.get_count() == 11
    value.count.value = 43
    assert value.get_count() == 43
    value.set_count(47)
    assert value.count.value == 47
    try:
        Existing(object_id)
    except ValueError as error:
        assert 'already bound' in str(error)
        pass
    else:
        raise AssertionError('duplicate existing-ID wrapper replaced the receiver')
    assert _native.inheritance_get(object_id) is value
    retained = value.count
    session, number = value.codec_session, value.svtypes_object_number
    svx.close_instance(value)
    svx.close_instance(value)
    assert session.get(number) is None
    try:
        _ = retained.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('existing-ID close revived field storage')

    retained_failed = []
    class Failed(Existing):
        def _svx_bind_active_projected_fields(self):
            super()._svx_bind_active_projected_fields()
            self.count.value = 53
            retained_failed.append(self.count)
            raise ValueError('existing field initialization failed')
    object_id = _native.inheritance_create_sv(class_id, encode_constructor(class_id, {}))
    try:
        Failed(object_id)
    except ValueError as error:
        assert str(error) == 'existing field initialization failed'
    else:
        raise AssertionError('failed wrapper unexpectedly succeeded')
    assert _native.inheritance_get(object_id) is None
    assert invoke_sv(object_id, class_id + '#get_count', {}) == 53
    try:
        _ = retained_failed[0].value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('failed wrapper retained active storage')
    replacement = Existing(object_id)
    assert replacement.count.value == 53
    svx.close_instance(replacement)
    svx.display('SVX_EXISTING_FIELD_VIEW_PASS')
