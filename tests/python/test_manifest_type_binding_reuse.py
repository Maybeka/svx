from copy import deepcopy

import pytest
import svtypes

from svx import inheritance
from tests.python.test_m8_inheritance import INT, manifest_data


def repeated_bindings():
    data = manifest_data()
    binding = {key: value for key, value in INT.items() if key != 'python'}
    binding['svtypes'] = svtypes.type_spec_identity(svtypes.Int)
    owner = data['classes'][0]
    method = owner['methods'][0]
    owner['methods'] = [dict(method, name=f'method_{index}', timing='function',
        canonical_id=f"{owner['canonical_id']}#method_{index}",
        parameters=[{'name': 'value', 'type': deepcopy(binding)}],
        return_type=deepcopy(binding)) for index in range(8)]
    return data


def test_intrinsic_metadata_is_checked_once_per_manifest_not_across_calls(monkeypatch):
    calls = []
    original = inheritance._codec_from_spec
    def codec(spec):
        if spec.get('svtypes') == {'kind': 'scalar', 'name': 'Int'}:
            calls.append(spec)
        return original(spec)
    monkeypatch.setattr(inheritance, '_codec_from_spec', codec)
    data = repeated_bindings()
    first = inheritance.parse_manifest(data)
    assert len(calls) == 1
    second = inheritance.parse_manifest(data)
    assert len(calls) == 2
    assert first == second
    left = original(first.classes[0].methods[0].parameters[0].type_binding.runtime_spec())
    right = original(first.classes[0].methods[1].parameters[0].type_binding.runtime_spec())
    assert left is not right, 'metadata reuse must not share mutable codec instances'


def test_changed_descriptor_and_type_spelling_are_not_hidden_by_reuse():
    for field, value, reason in [
        ('sv', 'bit [7:', 'invalid SystemVerilog type'),
        ('encoding_descriptor', {}, 'encoding_descriptor'),
    ]:
        data = repeated_bindings()
        data['classes'][0]['methods'][1]['parameters'][0]['type'][field] = value
        with pytest.raises(inheritance.SVXInheritanceError) as caught:
            inheritance.parse_manifest(data)
        message = str(caught.value)
        assert reason in message and "method 'method_1'" in message


def test_custom_type_metadata_is_never_memoized_and_scope_resets_on_error():
    calls = []
    @inheritance._reuse_intrinsic_binding
    def binding(value, where, *, allow_void):
        calls.append(value)
        return object()
    @inheritance._type_binding_scope
    def parse():
        raw = {'svtypes': {'kind': 'class', 'module': 'user_types', 'qualname': 'Payload'}}
        assert binding(raw, 'first', allow_void=False) is not binding(raw, 'second', allow_void=False)
        raise ValueError('stop')
    with pytest.raises(ValueError, match='stop'):
        parse()
    assert len(calls) == 2 and inheritance._type_binding_cache.get() is None


def test_artifact_inventory_does_not_rebuild_its_primed_records(monkeypatch):
    from collections import Counter
    model = inheritance.parse_manifest(repeated_bindings())
    python_sources = inheritance.emit_python_mirrors(model)
    sv_source = inheritance.emit_sv_mirrors(model)
    expected = inheritance.artifact_manifest(model, python_sources, sv_source)
    calls = Counter()
    original = inheritance._sv_record_type
    def record(owner, kind, fields):
        calls[(owner, kind)] += 1
        return original(owner, kind, fields)
    monkeypatch.setattr(inheritance, '_sv_record_type', record)
    assert inheritance.artifact_manifest(model, python_sources, sv_source) == expected
    assert calls and all(count == 1 for count in calls.values())


@pytest.mark.parametrize('annotation', [svtypes.Int, svtypes.Bit[8],
                                      svtypes.RemoteRef['sv://pkg/Target']])
def test_intrinsic_noncollections_do_not_materialize_for_typedef_detection(monkeypatch, annotation):
    codec = svtypes.materialize_type_spec(annotation, location='test')
    binding = inheritance._type_binding({
        'unified_type_name': svtypes.unified_type_name(codec),
        'svtypes': svtypes.type_spec_identity(annotation),
        'sv': svtypes.sv_type_expression(codec),
        'sv_packer': svtypes.sv_packer_expression(codec),
        'encoding_descriptor': svtypes.encoding_descriptor(codec).to_dict(),
    }, 'test', allow_void=False)
    def no_codec(spec):
        raise AssertionError('a scalar/packed/RemoteRef cannot need a collection typedef')
    monkeypatch.setattr(inheritance, '_codec_from_spec', no_codec)
    assert inheritance._sv_collection_typedef(binding) is None


def test_class_value_discovery_does_not_inspect_syntax_of_nonvalue_members():
    from types import SimpleNamespace
    from svx.sv_value_scan import SourceValues
    class Member:
        visibility = SimpleNamespace(name='Public')
        def __init__(self, kind):
            self.name = kind.lower()
            self.kind = SimpleNamespace(name=kind)
        @property
        def syntax(self):
            raise AssertionError('ordinary members cannot declare class-owned value types')
    class Scope:
        genericClass = None
        def __iter__(self):
            return iter(Member(kind) for kind in ('Subroutine', 'ClassProperty', 'MethodPrototype'))
    owner = Scope()
    values = SourceValues({})
    values.register_class_values(owner, 'pkg::Owner')
    assert values.class_value_members[(owner, 'pkg::Owner')] == []


def test_unused_class_value_graphs_are_deferred_and_flushed_in_original_order():
    from types import SimpleNamespace
    from svx.sv_value_scan import SourceValues
    visited = []
    class Scope:
        genericClass = None
        def __init__(self, name):
            self.name = name
        def __iter__(self):
            visited.append(self.name)
            return iter(())
    values = SourceValues({})
    values.modules = SimpleNamespace(annotations={})
    first, second = Scope('first'), Scope('second')
    values.register_class_values(first, 'pkg::First', defer=True)
    values.register_class_values(second, 'pkg::Second', defer=True)
    values.register_class_values(first, 'pkg::First', defer=True)
    values.publish_class_values(first, 'pkg::First')
    assert visited == []
    values._flush_class_values()
    assert visited == ['first', 'second'] and not values.pending_class_values


def test_deferred_class_values_match_eager_discovery_with_shared_generic_aliases(tmp_path, monkeypatch):
    from svx.declarations import manifest_from_declarations, manifest_dict
    from svx.sv_value_scan import SourceValues
    source = tmp_path / 'aliases.sv'
    source.write_text('''package p;
class G #(int WIDTH=8);
  typedef enum bit [WIDTH-1:0] { IDLE, READY } Mode;
endclass
class A;
  typedef G#(9) Shared;
endclass
class B;
  typedef G#(9) Shared;
  function Shared::Mode echo(Shared::Mode mode); return mode; endfunction
endclass
endpackage
''', encoding='utf-8')
    options = dict(sv_source_files=[source], sv_class_targets=['p::A', 'p::B'],
                   sv_member_targets=['echo'])
    deferred = manifest_from_declarations(**options)
    original = SourceValues.register_class_values
    def eager(self, native, prefix, **kwargs):
        return original(self, native, prefix, defer=False)
    monkeypatch.setattr(SourceValues, 'register_class_values', eager)
    reference = manifest_from_declarations(**options)
    assert manifest_dict(deferred) == manifest_dict(reference)
    assert inheritance.emit_python_mirrors(deferred) == inheritance.emit_python_mirrors(reference)
    assert inheritance.emit_sv_mirrors(deferred) == inheritance.emit_sv_mirrors(reference)
