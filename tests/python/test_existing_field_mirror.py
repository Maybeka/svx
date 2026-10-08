from pathlib import PurePosixPath

import pytest
from svtypes import ExternalStorageError, Int

from svx import _native
from svx import field_storage
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest
from tests.integration.sv_field_mirror_schema import manifest_data


def existing_field_manifest():
    data = manifest_data()
    data['classes'] = data['classes'][:1]
    del data['classes'][0]['constructor']
    return parse_manifest(data)


@pytest.mark.parametrize('name', ['bytes', 'operation', 'field_offset', 'field_value', 'error', 'ok', 'response'])
def test_field_dispatch_qualifies_members_that_shadow_generated_locals(name):
    data = manifest_data()
    data['classes'] = data['classes'][:1]
    binding = data['classes'][0]['fields'][0]['type']
    data['classes'][0]['fields'] = [{'name': name, 'type': binding}]
    text = emit_sv_mirrors(parse_manifest(data))
    assert f'int_packer::pack(this.{name}, bytes)' in text
    assert f'int_packer::unpack(this.{name}, bytes, field_offset)' in text
    assert f'int_packer::unpack(this.{name}, operation.payload, field_offset)' in text
    assert f'pack({name}, bytes)' not in text


@pytest.mark.parametrize('name', ['bytes', 'operation', 'field_value', 'field_insert'])
@pytest.mark.parametrize('kind', ['queue', 'dyn_array', 'fixed_array', 'assoc_array'])
def test_addressed_sequence_dispatch_qualifies_every_member_access(name, kind):
    import svtypes

    data = manifest_data()
    data['classes'] = data['classes'][:1]
    annotation = {
        'queue': svtypes.Queue[svtypes.Int],
        'dyn_array': svtypes.DynArray[svtypes.Int],
        'fixed_array': svtypes.Array[svtypes.Int, 3],
        'assoc_array': svtypes.AssocArray[svtypes.Int, svtypes.Int],
    }[kind]
    codec = annotation()
    binding = {
        'unified_type_name': svtypes.unified_type_name(codec),
        'svtypes': svtypes.type_spec_identity(annotation),
        'sv': svtypes.sv_type_expression(codec),
        'sv_packer': svtypes.sv_packer_expression(codec),
        'encoding_descriptor': svtypes.encoding_descriptor(codec).to_dict(),
    }
    data['classes'][0]['fields'] = [{'name': name, 'type': binding}]
    text = emit_sv_mirrors(parse_manifest(data))
    if kind == 'assoc_array':
        assert f'int_packer::pack(this.{name}[field_key], bytes)' in text
        assert f'this.{name}[field_key] = field_value;' in text
        assert f'this.{name}.exists(field_key)' in text
        assert f'this.{name}.delete(field_key);' in text
    else:
        assert f'int_packer::pack(this.{name}[operation.path_index[0]], bytes)' in text
        assert f'this.{name}[operation.path_index[0]] = field_value;' in text
        if kind == 'fixed_array':
            assert f'operation.path_index[0] < $size(this.{name})' in text
            assert f'this.{name}.size()' not in text
            return
        assert f'operation.path_index[0] <= this.{name}.size()' in text
        if kind == 'queue':
            assert f'this.{name}.insert(operation.path_index[0], field_value);' in text
            assert f'this.{name}.push_back(field_value);' in text
            assert f'this.{name}.delete(operation.path_index[0]);' in text
        else:
            assert f'field_delete[i] = this.{name}[i];' in text
            assert f'field_delete[i - 1] = this.{name}[i];' in text
            assert f'this.{name} = field_insert;' in text


def test_fixed_array_field_bounds_are_valid_systemverilog():
    pytest.importorskip('pyslang')
    from pyslang.ast import Compilation
    from pyslang.syntax import SyntaxTree
    import re
    import svtypes

    data = manifest_data()
    data['classes'] = data['classes'][:1]
    annotation = svtypes.Array[svtypes.Int, 3]
    codec = annotation()
    data['classes'][0]['fields'] = [{'name': 'bytes', 'type': {
        'unified_type_name': svtypes.unified_type_name(codec),
        'svtypes': svtypes.type_spec_identity(annotation),
        'sv': svtypes.sv_type_expression(codec),
        'sv_packer': svtypes.sv_packer_expression(codec),
        'encoding_descriptor': svtypes.encoding_descriptor(codec).to_dict(),
    }}]
    text = emit_sv_mirrors(parse_manifest(data))
    bounds = re.findall(r'operation.path_index\[0\] < (.*?)\) begin', text)
    assert len(bounds) == 6  # deep resolver plus read/set in both gateways
    for bound in bounds:
        compilation = Compilation()
        compilation.addSyntaxTree(SyntaxTree.fromText(
            'class Probe; int bytes[3]; function bit check(longint unsigned index); '
            f'return index < {bound}; endfunction endclass'
        ))
        assert not [diagnostic for diagnostic in compilation.getAllDiagnostics() if diagnostic.isError()]
    invalid = Compilation()
    invalid.addSyntaxTree(SyntaxTree.fromText(
        'class Probe; int bytes[3]; function bit check(longint unsigned index); '
        'return index < this.bytes.size(); endfunction endclass'
    ))
    assert any(diagnostic.isError() for diagnostic in invalid.getAllDiagnostics())


def test_constructorless_field_view_preserves_existing_id_contract():
    manifest = existing_field_manifest()
    text = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/field_owner_pkg.py')]
    assert 'class Base(SVMirror):' in text
    assert 'count = _codec_from_spec(' in text
    assert 'def __init__(self, remote_object_id: int):' in text
    assert 'inheritance_create_sv(' not in text
    assert 'register_constructor(' not in text
    assert 'sv://field_owner_pkg/Base.count' in text
    # Wrapping a registered endpoint must not request a new physical helper.
    assert 'class Base extends' not in emit_sv_mirrors(manifest)


def generated_view():
    text = emit_python_mirrors(existing_field_manifest())[
        PurePosixPath('svx_mirror/field_owner_pkg.py')]
    namespace = {'__name__': 'tests.generated_existing_field_mirror'}
    exec(compile(text, '<generated existing field mirror>', 'exec'), namespace)
    return namespace['Base']


def test_existing_field_view_binds_without_allocation_and_retires_storage(monkeypatch):
    registry = {}
    class Transport:
        payload = Int().pack(11)
        def read_field(self, object_id, field_id, descriptor, path):
            assert (object_id, field_id, path) == (71, 'sv://field_owner_pkg/Base.count', '[]')
            return self.payload
        def write_field(self, object_id, field_id, descriptor, path, operation, payload):
            assert operation == 'set'
            self.payload = payload
    transport = Transport()
    storage_type = field_storage.SVXFieldStorage
    monkeypatch.setattr(field_storage, 'SVXFieldStorage', lambda: storage_type(transport))
    monkeypatch.setattr(_native, 'inheritance_bind', lambda key, value: registry.update({key: value}))
    monkeypatch.setattr(_native, 'inheritance_create_sv', lambda *args: pytest.fail('allocated a second endpoint'))
    Base = generated_view()
    value = Base(71)
    assert registry[71] is value
    retained = value.count
    assert retained.value == 11
    retained.value = 19
    assert value.count.value == 19
    value._svx_release_projected_fields()
    with pytest.raises(ExternalStorageError):
        _ = retained.value


def test_existing_field_view_failed_binding_does_not_destroy_sv_endpoint(monkeypatch):
    registry = {}
    retired = []
    monkeypatch.setattr(_native, 'inheritance_bind', lambda key, value: registry.update({key: value}))
    monkeypatch.setattr(_native, 'inheritance_unbind', lambda key: (retired.append(key), registry.pop(key)))
    monkeypatch.setattr(_native, 'inheritance_close', lambda *args: pytest.fail('destroyed existing SV endpoint'))
    Base = generated_view()
    original = ValueError('binding failed')
    def fail(self):
        raise original
    monkeypatch.setattr(Base, '_svx_bind_active_projected_fields', fail)
    with pytest.raises(ValueError) as error:
        Base(71)
    assert error.value is original
    assert not registry
    assert retired == [71]


def test_existing_field_view_duplicate_binding_preserves_previous_receiver(monkeypatch):
    old = object()
    registry = {71: old}
    def bind(key, value):
        raise RuntimeError('duplicate binding')
    monkeypatch.setattr(_native, 'inheritance_bind', bind)
    monkeypatch.setattr(_native, 'inheritance_unbind', lambda *args: pytest.fail('removed previous receiver'))
    with pytest.raises(RuntimeError, match='duplicate binding'):
        generated_view()(71)
    assert registry[71] is old


def test_existing_field_view_subclass_does_not_change_constructor_selection(monkeypatch):
    from svx import inheritance
    monkeypatch.setattr(inheritance, 'register_python_subclass',
                        lambda *args: pytest.fail('changed constructor selection'))
    Base = generated_view()
    class Derived(Base):
        pass
    assert issubclass(Derived, Base)
