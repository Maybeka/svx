from __future__ import annotations

import svtypes
import svx
from svx.errors import SVXRemoteError

Item = svtypes.RemoteRef['sv://handle_collection_pkg/Item']
Vif = svtypes.RemoteRef['sv-vif://handle_collection_if/master']
_calls = 0
_vif_calls = 0
_constructed = []


def checked(values):
    global _calls
    _calls += 1
    return values


def references(value):
    if isinstance(value, dict):
        return {key: references(item) for key, item in value.items()}
    if isinstance(value, list):
        return [references(item) for item in value]
    reference = getattr(value, '_svx_remote_reference', value)
    if reference.object_number:
        assert value._svx_vif_target_type_name == 'sv-vif://handle_collection_if/master'
    return reference


def checked_vif(values, result):
    global _vif_calls
    assert references(values) == references(result)
    _vif_calls += 1
    return result


@svx.sv_mirror('sv://handle_collection_pkg/Owner')
class OwnerStub(svx.SVMirror):
    pass


@svx.sv_mirror('sv://handle_collection_pkg/ConstructorOwner')
class ConstructorStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class ConstructorDerived(ConstructorStub):
    def __init__(self, items: svtypes.Queue[Item],
                 groups: svtypes.AssocArray[svtypes.String, svtypes.Queue[Item]],
                 ports: svtypes.Queue[Vif]):
        super().__init__(items, groups, ports)
        assert list(self.get_items()) == list(items)
        assert dict(self.get_groups()) == dict(groups)
        output = svx.Output()
        self.get_ports(output)
        assert references(output.value) == references(ports)
        self.arguments = (items, groups, ports)
        _constructed.append(self)


@svx.inheritance_class()
class Derived(OwnerStub):
    @svx.inheritance_method
    def vif_queue_echo(self, values: svtypes.Queue[Vif], result: svx.Output[svtypes.Queue[Vif]]) -> svx.Function:
        super().vif_queue_echo(values, result)
        checked_vif(values, result.value)

    @svx.inheritance_method
    def vif_dynamic_echo(self, values: svtypes.DynArray[Vif], result: svx.Output[svtypes.DynArray[Vif]]) -> svx.Function:
        super().vif_dynamic_echo(values, result)
        checked_vif(values, result.value)

    @svx.inheritance_method
    def vif_fixed_echo(self, values: svtypes.Array[Vif, 2], result: svx.Output[svtypes.Array[Vif, 2]]) -> svx.Function:
        super().vif_fixed_echo(values, result)
        checked_vif(values, result.value)

    @svx.inheritance_method
    def vif_associative_echo(self, values: svtypes.AssocArray[svtypes.String, Vif], result: svx.Output[svtypes.AssocArray[svtypes.String, Vif]]) -> svx.Function:
        super().vif_associative_echo(values, result)
        checked_vif(values, result.value)

    @svx.inheritance_method
    def vif_nested_echo(self, values: svtypes.AssocArray[svtypes.String, svtypes.Queue[Vif]], result: svx.Output[svtypes.AssocArray[svtypes.String, svtypes.Queue[Vif]]]) -> svx.Function:
        super().vif_nested_echo(values, result)
        checked_vif(values, result.value)

    @svx.inheritance_method
    def vif_transform(self, values: svtypes.Queue[Vif], observed: svx.Output[svtypes.Queue[Vif]],
                      changed: svx.Inout[svtypes.Queue[Vif]]) -> svx.Function:
        super().vif_transform(values, observed, changed)
        assert references(observed.value) == references(changed.value) == references(values)
        checked_vif(values, observed.value)

    @svx.inheritance_method
    def queue_echo(self, values: svtypes.Queue[Item]) -> svx.Function[svtypes.Queue[Item]]:
        return checked(super().queue_echo(values))

    @svx.inheritance_method
    def dynamic_echo(self, values: svtypes.DynArray[Item]) -> svx.Function[svtypes.DynArray[Item]]:
        return checked(super().dynamic_echo(values))

    @svx.inheritance_method
    def fixed_echo(self, values: svtypes.Array[Item, 2]) -> svx.Function[svtypes.Array[Item, 2]]:
        return checked(super().fixed_echo(values))

    @svx.inheritance_method
    def associative_echo(self, values: svtypes.AssocArray[svtypes.String, Item]) -> svx.Function[svtypes.AssocArray[svtypes.String, Item]]:
        return checked(super().associative_echo(values))

    @svx.inheritance_method
    def nested_echo(self, values: svtypes.AssocArray[svtypes.String, svtypes.Queue[Item]]) -> svx.Function[svtypes.AssocArray[svtypes.String, svtypes.Queue[Item]]]:
        return checked(super().nested_echo(values))

    @svx.inheritance_method
    def transform(self, values: svtypes.Queue[Item], observed: svx.Output[svtypes.Queue[Item]],
                  changed: svx.Inout[svtypes.Queue[Item]]) -> svx.Function[svtypes.Queue[Item]]:
        result = super().transform(values, observed, changed)
        return checked(result)


@svx.export(name='handle_collection.create')
def create():
    global _instance
    first, = _constructed
    second = ConstructorDerived(*first.arguments)
    assert len(_constructed) == 2
    items, groups, ports = first.arguments
    invalid_item = svtypes.RemoteRefValue('sv://handle_collection_pkg/Item', (1 << 63))
    invalid_port = svtypes.RemoteRefValue('sv-vif://handle_collection_if/master', (1 << 63))
    for arguments in (([invalid_item], groups, ports),
                      (items, {'invalid': [invalid_item]}, ports),
                      (items, groups, [invalid_port])):
        try:
            ConstructorDerived(*arguments)
        except RuntimeError as error:
            assert 'external handle' in str(error)
        else:
            raise AssertionError('unknown constructor handle accepted')
    assert len(_constructed) == 2
    svx.publish_object('handle_collection.constructor', second)
    svx.display('HANDLE_COLLECTION_CONSTRUCTOR_PYTHON_PASS')
    _instance = Derived()
    values = list(_instance.seed())
    assert values[0].object_number == values[2].object_number != 0
    assert values[1].object_number == 0
    _instance.queue_handles.value = values
    assert list(_instance.queue_handles.value) == values
    fields = {'first': values, 'empty': []}
    _instance.nested_handles.value = fields
    assert dict(_instance.nested_handles.value) == fields
    _instance.nested_handles.value['first'][1] = values[0]
    assert _instance.nested_handles.value['first'][1] == values[0]
    assert list(_instance.nested_handles.value['empty']) == []
    assert list(_instance.queue_handles.value) == values
    _instance.nested_handles.value['first'][1] = values[1]
    _instance.nested_handles.value['replacement'] = [values[2]]
    assert list(_instance.nested_handles.value['replacement']) == [values[2]]
    before = list(_instance.queue_handles.value)
    try:
        _instance.queue_handles.value = [svtypes.RemoteRefValue('sv://handle_collection_pkg/Item', (1 << 63))]
    except svtypes.ExternalStorageError:
        pass
    else:
        raise AssertionError('unknown handle field element accepted')
    assert list(_instance.queue_handles.value) == before
    try:
        _instance.nested_handles.value['first'][0] = svtypes.RemoteRefValue('sv://handle_collection_pkg/Item', (1 << 63))
    except svtypes.ExternalStorageError:
        pass
    else:
        raise AssertionError('unknown nested handle field element accepted')
    assert _instance.nested_handles.value['first'][0] == values[0]
    port_references = [getattr(port, '_svx_remote_reference', port) for port in first.arguments[2]]
    _instance.vif_handles.value = port_references
    assert list(_instance.vif_handles.value) == port_references
    _instance.vif_handles.value[1] = port_references[2]
    assert _instance.vif_handles.value[1] == port_references[2]
    _instance.vif_handles.value[1] = port_references[1]
    for sequence in (_instance.queue_handles.value,
                     _instance.nested_handles.value['first'],
                     _instance.vif_handles.value):
        saved = list(sequence)
        sequence.append(None)
        assert sequence.pop().object_number == 0
        sequence.insert(0, None)
        assert sequence.pop(0).object_number == 0
        sequence.append(saved[0])
        sequence.insert(1, saved[0])
        del sequence[1]
        assert sequence.pop() == saved[0]
        assert list(sequence) == saved
    _instance.dynamic_handles.value = values[:2]
    dynamic = _instance.dynamic_handles.value
    dynamic.append(values[2])
    dynamic.insert(1, values[0])
    del dynamic[1]
    assert dynamic.pop() == values[2]
    assert list(dynamic) == values[:2]
    del _instance.nested_handles.value['replacement']
    assert dict(_instance.nested_handles.value) == fields
    invalid = svtypes.RemoteRefValue('sv://handle_collection_pkg/Item', (1 << 63))
    for sequence in (_instance.queue_handles.value, dynamic,
                     _instance.nested_handles.value['first']):
        saved = list(sequence)
        try:
            sequence.append(invalid)
        except svtypes.ExternalStorageError:
            pass
        else:
            raise AssertionError('unknown appended handle accepted')
        assert list(sequence) == saved

    from svx.field_storage import FieldStorageKey

    def resize(name, codec, path, length):
        _instance._svx_field_storage.write(
            FieldStorageKey(_instance._svx_remote_object_id, f'sv://handle_collection_pkg/Owner.{name}'),
            svtypes.FieldDescriptor(codec), path, svtypes.FieldOperation.RESIZE, svtypes.Int().pack(length))

    resize('dynamic_handles', svtypes.DynArray[Item](), svtypes.FieldPath(), 5)
    assert list(dynamic)[:2] == values[:2]
    assert [value.object_number for value in list(dynamic)[2:]] == [0, 0, 0]
    resize('dynamic_handles', svtypes.DynArray[Item](), svtypes.FieldPath(), 2)
    resize('queue_handles', svtypes.Queue[Item](), svtypes.FieldPath(), 5)
    assert list(_instance.queue_handles.value)[:3] == values
    assert [value.object_number for value in list(_instance.queue_handles.value)[3:]] == [0, 0]
    resize('queue_handles', svtypes.Queue[Item](), svtypes.FieldPath(), 3)
    resize('nested_handles', svtypes.AssocArray[svtypes.String, svtypes.Queue[Item]](),
           svtypes.FieldPath().key(svtypes.String(), 'first'), 5)
    assert list(_instance.nested_handles.value['first'])[:3] == values
    assert list(_instance.nested_handles.value['empty']) == []
    resize('nested_handles', svtypes.AssocArray[svtypes.String, svtypes.Queue[Item]](),
           svtypes.FieldPath().key(svtypes.String(), 'first'), 3)
    _instance.matrix_handles.value = [values, []]
    matrix = _instance.matrix_handles.value
    matrix.append([values[0]])
    matrix.insert(1, [values[2]])
    assert list(matrix[1]) == [values[2]]
    del matrix[1]
    assert matrix.pop() == [values[0]]
    matrix[1].append(values[0])
    assert list(matrix[0]) == values
    assert list(matrix[1]) == [values[0]]
    resize('matrix_handles', svtypes.Queue[svtypes.Queue[Item]](), svtypes.FieldPath(), 3)
    assert list(matrix[2]) == []
    resize('matrix_handles', svtypes.Queue[svtypes.Queue[Item]](), svtypes.FieldPath(), 2)
    saved_matrix = [list(row) for row in matrix]
    try:
        matrix.append([invalid])
    except svtypes.ExternalStorageError:
        pass
    else:
        raise AssertionError('unknown appended subcontainer handle accepted')
    assert [list(row) for row in matrix] == saved_matrix
    for name, codec in (('queue_handles', svtypes.Queue[Item]()),
                        ('dynamic_handles', svtypes.DynArray[Item]())):
        try:
            resize(name, codec, svtypes.FieldPath(), -1)
        except RuntimeError as error:
            assert 'nonnegative' in str(error)
        else:
            raise AssertionError('negative resize accepted')
    assert list(_instance.queue_handles.value) == values
    assert list(dynamic) == values[:2]
    svx.display('HANDLE_COLLECTION_FIELD_MUTATION_PASS')
    svx.display('HANDLE_COLLECTION_FIELD_PYTHON_PASS')
    assert list(_instance.queue_echo(values)) == values
    assert list(_instance.dynamic_echo(values)) == values
    assert list(_instance.fixed_echo(values[:2])) == values[:2]
    associative = dict(_instance.associative_echo({'first': values[0], 'null': values[1]}))
    assert associative == {'first': values[0], 'null': values[1]}, (associative, values)
    nested = {'first': values, 'empty': []}
    assert dict(_instance.nested_echo(nested)) == nested
    observed, changed = svx.Output(), svx.Inout([])
    assert list(_instance.transform(values, observed, changed)) == values
    assert list(observed.value) == list(changed.value) == values
    calls_before = _calls
    try:
        _instance.queue_echo([values[0], svtypes.RemoteRefValue('sv://handle_collection_pkg/Item', (1 << 63))])
    except SVXRemoteError:
        pass
    else:
        raise AssertionError('unknown handle ID reached the SV method')
    assert _calls == calls_before
    svx.display('HANDLE_COLLECTION_REJECT_PASS')
    svx.publish_object('handle_collection.instance', _instance)
    svx.display('HANDLE_COLLECTION_PYTHON_PASS')


@svx.export(name='handle_collection.close')
def close():
    assert _calls == 12
    assert _vif_calls == 6
    svx.display('VIF_COLLECTION_PYTHON_PASS')
    svx.close_instance(_instance)
    for instance in _constructed:
        svx.close_instance(instance)
    svx.display('HANDLE_COLLECTION_CLOSE_PASS')
