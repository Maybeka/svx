from copy import deepcopy

import pytest

from svx.declarations import _source_semantic_type_declaration, manifest_dict
from svx.errors import SVXInheritanceError
from svx.inheritance import (
    REQUIRED_RUNTIME_CAPABILITIES, EXTERNAL_FIELD_STORAGE_CAPABILITY,
    emit_sv_mirrors, parse_manifest,
)
from svx.sv_scan import discover_sv_class_declarations, validate_sv_declarations


def discover(tmp_path):
    pytest.importorskip('pyslang')
    source = tmp_path / 'handles.sv'
    source.write_text('''package collection_types;
      class Item; int value; endclass
      typedef Item queue_t[$];
      typedef Item dynamic_t[];
      typedef Item fixed_t[2];
      typedef Item associative_t[string];
      typedef queue_t nested_t[string];
      typedef queue_t matrix_t[$];
      class Owner;
        queue_t handles;
        dynamic_t dynamic_handles;
        nested_t groups;
        matrix_t matrix;
        virtual function queue_t queue_echo(input queue_t values); return values; endfunction
        virtual function dynamic_t dynamic_echo(input dynamic_t values); return values; endfunction
        virtual function fixed_t fixed_echo(input fixed_t values); return values; endfunction
        virtual function associative_t associative_echo(input associative_t values); return values; endfunction
        virtual function nested_t nested_echo(input nested_t values); return values; endfunction
      endclass
    endpackage''')
    classes = discover_sv_class_declarations([source], ['sv://collection_types/Owner'],
                                             _source_semantic_type_declaration)
    for cls in classes:
        assert cls.pop('discovery_base_id') is None
    return parse_manifest({
        'schema_uri': 'https://svx.dev/schema/inheritance-manifest/v2',
        'schema_version': '2.0.0', 'generator_abi_version': 2,
        'required_runtime_capabilities': [*REQUIRED_RUNTIME_CAPABILITIES, EXTERNAL_FIELD_STORAGE_CAPABILITY],
        'classes': classes,
    })


def test_handle_collections_retain_codec_shape_and_native_leaf(tmp_path):
    manifest = discover(tmp_path)
    for method in manifest.classes[0].methods:
        parameter = method.parameters[0]
        assert parameter.handle.sv_type == 'collection_types::Item'
        assert parameter.handle.target_type_name == 'sv://collection_types/Item'
        assert parameter.handle.collection_binding == parameter.type_binding
        assert method.return_handle.collection_binding == method.return_type
    restored = parse_manifest(manifest_dict(manifest))
    assert restored == manifest


def test_generated_collections_convert_elements_through_scalar_registry(tmp_path):
    text = emit_sv_mirrors(discover(tmp_path))
    assert 'typedef remote_ref wire_0[$];' in text
    assert 'typedef remote_ref wire_0[];' in text
    assert 'typedef remote_ref wire_0[2];' in text
    assert 'typedef remote_ref wire_0[string];' in text
    assert 'typedef wire_0 wire_1[string];' in text
    assert 'SVXExternal_sv___collection_types_Item::encode' in text
    assert 'SVXExternal_sv___collection_types_Item::decode' in text
    assert 'converted.push_back(element_0)' in text
    assert 'converted = new[value.size()]' in text
    assert 'converted.delete()' in text
    assert 'value = converted;' in text
    assert 'coverpoint value' not in text


def test_collection_field_root_uses_wire_container_not_native_source_alias(tmp_path):
    text = emit_sv_mirrors(discover(tmp_path))
    assert '::wire_type field_wire;' in text
    assert 'collection_types::queue_t field_wire;' not in text
    assert 'collection_types::nested_t field_wire;' not in text
    assert '::decode(field_wire, field_native, error)' in text
    assert 'this.handles = field_native;' in text
    assert 'this.groups = field_native;' in text
    root_set = text.split('"sv://collection_types/Owner.handles@svx_field_set": begin', 1)[1]
    root_set = root_set.split('"sv://collection_types/Owner.handles@svx_field_operation": begin', 1)[0]
    assert 'field_wire = new(' not in root_set
    assert 'this.handles[operation.path_index[0]] = field_native;' in text
    assert 'this.groups[field_key_0][operation.path_index[1]] = field_native;' in text


def test_handle_field_mutations_use_native_temporaries_and_addressed_containers(tmp_path):
    text = emit_sv_mirrors(discover(tmp_path))
    assert 'this.handles.push_back(field_element);' in text
    assert 'this.handles.insert(operation.path_index[0], field_element);' in text
    assert 'this.handles.delete(operation.path_index[0]);' in text
    assert 'this.groups[field_key_0].push_back(field_element);' in text
    assert 'this.groups.delete(field_key_0);' in text
    assert 'this.matrix.push_back(field_element);' in text
    assert 'this.matrix[operation.path_index[0]].push_back(field_element);' in text
    assert '::decode_0(field_wire, field_element, error)) begin' in text
    assert 'field_sequence = new[this.dynamic_handles.size() + 1](this.dynamic_handles);' in text
    assert 'this.dynamic_handles = new[field_length](this.dynamic_handles);' in text
    assert 'while (this.handles.size() < field_length) this.handles.push_back(field_default);' in text
    assert '::decode(field_wire, field_element, error)) begin' in text


def test_collection_handle_target_mismatch_rejects(tmp_path):
    data = deepcopy(manifest_dict(discover(tmp_path)))
    data['classes'][0]['methods'][0]['parameters'][0]['handle']['target_type_name'] = 'sv://collection_types/Other'
    with pytest.raises(SVXInheritanceError, match='must match the SvTypes RemoteRef target'):
        parse_manifest(data)


@pytest.mark.parametrize('dimensions', ['[$]', '[]', '[2]', '[string]', '[string][$]'])
def test_native_handle_formals_without_source_typedef(tmp_path, dimensions):
    pytest.importorskip('pyslang')
    source = tmp_path / 'native_formals.sv'
    source.write_text(f'''package native_formals;
      class Item; endclass
      class Owner;
        function new(input Item initial_values{dimensions}); endfunction
        virtual function void echo(input Item values{dimensions},
                                   output Item result{dimensions},
                                   inout Item changed{dimensions});
          result = values; changed = values;
        endfunction
      endclass
    endpackage''')
    classes = discover_sv_class_declarations([source], ['sv://native_formals/Owner'],
                                             _source_semantic_type_declaration)
    for cls in classes:
        cls.pop('discovery_base_id')
    validate_sv_declarations(classes, [source])
    manifest = parse_manifest({
        'schema_uri': 'https://svx.dev/schema/inheritance-manifest/v2',
        'schema_version': '2.0.0', 'generator_abi_version': 2,
        'required_runtime_capabilities': list(REQUIRED_RUNTIME_CAPABILITIES),
        'classes': classes,
    })
    text = emit_sv_mirrors(manifest)
    assert 'typedef native_formals::Item native_0' in text
    assert '::native_type values' in text
    assert '::native_type result' in text
    assert '::native_type changed' in text
    assert len(manifest.classes[0].methods[0].parameters) == 3
    assert manifest.classes[0].constructor.parameters[0].handle.collection_binding is not None


def test_nested_vif_views_encode_decode_without_changing_shape(monkeypatch):
    import svtypes
    from svx import inheritance

    target = 'sv-vif://collection_bus/master'

    class View:
        _svx_vif_target_type_name = target

        def __init__(self, reference):
            self._svx_remote_reference = reference

    monkeypatch.setitem(inheritance._vif_views, target, View)
    reference = svtypes.RemoteRefValue(target, 17)
    null = svtypes.RemoteRefValue(target, 0)
    ordinary = svtypes.RemoteRefValue('sv://collection_types/Item', 9)
    raw = {'ports': [reference, null, reference], 'tuple': (reference, ordinary), 'empty': []}
    decoded = inheritance._decode_vif_view(raw)
    assert isinstance(decoded['ports'][0], View)
    assert isinstance(decoded['ports'][2], View)
    assert decoded['ports'][1] is null
    assert isinstance(decoded['tuple'], tuple)
    assert decoded['tuple'][1] is ordinary
    assert inheritance._encode_vif_view(decoded) == raw
    assert raw['ports'][0] is reference


def test_vif_container_return_keeps_native_function_prototype(tmp_path):
    pytest.importorskip('pyslang')
    source = tmp_path / 'returned_vifs.sv'
    source.write_text('''interface returned_bus; logic value; modport master(input value); endinterface
    package returned_vif_types;
      typedef virtual returned_bus.master port_t;
      typedef port_t ports_t[$];
      class Owner;
        virtual function ports_t echo(input ports_t values); return values; endfunction
      endclass
    endpackage''')
    classes = discover_sv_class_declarations([source], ['sv://returned_vif_types/Owner'],
                                             _source_semantic_type_declaration)
    for cls in classes:
        assert cls.pop('discovery_base_id') is None
    manifest = parse_manifest({
        'schema_uri': 'https://svx.dev/schema/inheritance-manifest/v2',
        'schema_version': '2.0.0', 'generator_abi_version': 2,
        'required_runtime_capabilities': list(REQUIRED_RUNTIME_CAPABILITIES),
        'classes': classes,
    })
    text = emit_sv_mirrors(manifest)
    assert 'virtual function returned_vif_types::ports_t echo(input returned_vif_types::ports_t values);' in text
    assert manifest.classes[0].methods[0].return_handle.kind == 'virtual_interface'
    assert len(manifest.classes[0].methods[0].parameters) == 1
