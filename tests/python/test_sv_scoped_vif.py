import io
import json
from pathlib import Path

import pytest

from svx.cli import main

pytest.importorskip('pyslang')


@pytest.mark.parametrize('container', ['unit', 'module', 'interface', 'program', 'generate'])
@pytest.mark.parametrize('named_fields', [False, True])
@pytest.mark.parametrize('aliased_operations', [False, True])
def test_scoped_vif_export_uses_shared_typed_endpoint_records(tmp_path, container, named_fields, aliased_operations):
    directory = Path(__file__).resolve().parents[1] / 'integration'
    body = (directory / 'scoped_vif_classes.svh').read_text(encoding='utf-8')
    if named_fields:
        for name in ('Owner', 'Consumer'):
            body = body.replace('class ' + name + ';', 'class ' + name + ';\n'
                                'typedef enum bit[1:0] {IDLE,ACTIVE} State; State state;')
    bus = (directory / ('scoped_alias_bus_if.sv' if aliased_operations else 'scoped_bus_if.sv')).read_text(encoding='utf-8')
    instances = ''
    if container == 'unit':
        definition, selectors = body, ['Owner', 'Consumer']
    else:
        native = 'module' if container == 'generate' else container
        if container == 'generate':
            body = 'for(genvar i=0;i<1;i++)begin:lane\n' + body + '\nend'
        definition = native + ' owner #(int W=8);\n' + body + '\nend' + native
        instances = 'owner a(), b(); owner#(13)c();'
        prefix = 'tb.*' + ('.lane[0]' if container == 'generate' else '')
        selectors = [prefix + '.Owner', prefix + '.Consumer']
    source = tmp_path / 'original.sv'
    source.write_text(bus + '\n' + definition + '\nmodule tb;scoped_bus_if bus0(),bus1();'
                      + instances + 'endmodule', encoding='utf-8')
    root = tmp_path / 'generated'
    arguments = ['export', '--class', *selectors, '--sv-source', str(source), '--out', str(root)]
    main(arguments, out=io.StringIO())
    main([*arguments, '--check'], out=io.StringIO())
    artifact = json.loads((root / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['systemverilog_compile_order'][0] == 'sv/native_handles.sv'
    text = (root / 'sv/native_handles.sv').read_text(encoding='utf-8')
    assert 'virtual scoped_bus_if' not in text
    assert 'SVXNativeHandleType value;' in text
    assert 'this.value.write(' in text
    if aliased_operations:
        assert 'scoped_bus_types_pkg::' not in text
        assert 'this.value.echo_map(' in text
        assert 'this.value.exchange_values(' in text
    from svx.inheritance import _call_record_class_name, _handle_adapter_stem, _manifest_handle_bindings, load_manifest
    model = load_manifest(root / 'inheritance.json')
    vif = next(binding for binding in _manifest_handle_bindings(model) if binding.collection_binding is None)
    record = _call_record_class_name('sv-vif://scoped_bus_if/master#write', 'request')
    assert text.index('class ' + record) < text.index('class ' + _handle_adapter_stem(vif) + 'Endpoint')
    manifest = json.loads((root / 'inheritance.json').read_text(encoding='utf-8'))
    assert all(cls['symbol'] != 'SVXVifRecords' for cls in manifest['classes'])
    target_ids = {field['handle']['target_type_name'] for cls in manifest['classes']
                  for field in cls.get('fields', []) if 'handle' in field}
    assert target_ids == {'sv-vif://scoped_bus_if/master'}
    if named_fields and container == 'module':
        original = (root / 'sv/source.sv').read_text(encoding='utf-8')
        assert original.count('typedef Owner::State SVXNativeValue_') == 1
        assert original.count('typedef Consumer::State SVXNativeValue_') == 1
    if named_fields and container == 'generate':
        original = (root / 'sv/source.sv').read_text(encoding='utf-8')
        assert 'class SVXLocalEnumPacker_' in original
        assert 'svtypes_pkg::bit_packer#(SVXInstanceValue_' not in original
        assert 'svtypes_pkg::bit_packer#(bit [1:0])::unpack(bits, bytes, offset);' in original
        assert original.count('typedef enum bit[1:0] {IDLE,ACTIVE} State;') == 2


def test_scoped_vif_operation_aliases_use_the_same_portable_wire_contract():
    from dataclasses import replace
    from svx.inheritance import ForeignClass, HandleBinding, Manifest, Method, Parameter, VifOperation, _type_binding
    from svx.declarations import _type_declaration
    from svx.native_handles import _portable_operations, _portable_vif_manifest, _targets
    import svtypes
    binding = _type_binding(_type_declaration(svtypes.Bit[8], where='value'), 'value', allow_void=False)
    method = Method('vif#write', 'write', (Parameter('value', binding, 'input'),),
                    None, None, 'task', False, False, False)
    operation = VifOperation(method=method, operation='task', sv_member_name='write')
    vif = HandleBinding('virtual_interface', 'sv-vif://bus/master', 'virtual bus.master', (operation,))
    assert _portable_operations(vif)
    aliased = replace(binding, sv='owner_pkg::Byte')
    changed = replace(method, parameters=(replace(method.parameters[0], type_binding=aliased),))
    alias_vif = replace(vif, operations=(replace(operation, method=changed),))
    assert _portable_operations(alias_vif)
    reference = _type_binding(_type_declaration(svtypes.RemoteRef[vif.target_type_name], where='bus'),
                              'bus', allow_void=False)
    outer = replace(method, parameters=(), return_type=reference, return_handle=alias_vif)
    owner = ForeignClass('sv://unit/0/Owner', 'sv', '$unit::Owner', (outer,), None)
    manifest = Manifest('', '', 2, (), (owner,))
    token = _targets.set(frozenset({vif.target_type_name}))
    try:
        rendered = _portable_vif_manifest(manifest)
    finally:
        _targets.reset(token)
    actual = rendered.classes[0].methods[0].return_handle.operations[0].method.parameters[0].type_binding
    assert actual.sv == svtypes.sv_type_expression(svtypes.Bit[8]())
    assert actual.runtime_spec() == aliased.runtime_spec()
    assert actual.encoding_descriptor == aliased.encoding_descriptor
    assert alias_vif.operations[0].method.parameters[0].type_binding.sv == 'owner_pkg::Byte'


def test_failed_handle_classification_does_not_leak_codegen_context(monkeypatch):
    from svx.inheritance import ForeignClass, Manifest, SCHEMA_URI, SCHEMA_VERSION
    from svx.errors import SVXInheritanceError
    import svx.native_handles as handles
    source = ForeignClass('sv://unit/0/Owner', 'sv', '$unit::Owner', (), None,
                          source_scope_json=json.dumps({'kind': 'compilation_unit', 'index': 0}))
    manifest = Manifest(SCHEMA_URI, SCHEMA_VERSION, 2, (), (source,))
    original = handles._targets.get(), handles._aliases.get(), handles._record_targets.get(), handles._nominal_types.get()
    def fail(manifest):
        raise SVXInheritanceError('classification failed')
    monkeypatch.setattr(handles, '_portable_handle_records', fail)
    @handles.with_native_handle_adapters
    def emit(manifest):
        pytest.fail('emitter must not run after classification failure')
    with pytest.raises(SVXInheritanceError, match='classification failed'):
        emit(manifest)
    assert (handles._targets.get(), handles._aliases.get(), handles._record_targets.get(), handles._nominal_types.get()) == original


@pytest.mark.parametrize('container', ['unit', 'module', 'interface', 'program', 'generate'])
def test_scoped_vif_nominal_operations_bind_explicit_native_types(tmp_path, container):
    directory = Path(__file__).resolve().parents[1] / 'integration'
    body = (directory / 'scoped_vif_classes.svh').read_text(encoding='utf-8')
    bus = (directory / 'scoped_nominal_bus_if.sv').read_text(encoding='utf-8')
    if container == 'unit':
        definition, instances, selectors = body, '', ['Owner', 'Consumer']
    else:
        native = 'module' if container == 'generate' else container
        if container == 'generate':
            body = 'for(genvar i=0;i<1;i++)begin:lane\n' + body + '\nend'
        definition = native + ' owner #(int W=8);\n' + body + '\nend' + native
        instances = 'owner a(), b(); owner#(13)c();'
        prefix = 'tb.*' + ('.lane[0]' if container == 'generate' else '')
        selectors = [prefix + '.Owner', prefix + '.Consumer']
    source = tmp_path / 'original.sv'
    source.write_text(bus + '\n' + definition + '\nmodule tb;scoped_bus_if bus0(),bus1();'
                      + instances + 'endmodule', encoding='utf-8')
    root = tmp_path / 'generated'
    arguments = ['export', '--class', *selectors, '--sv-source', str(source), '--out', str(root)]
    main(arguments, out=io.StringIO())
    before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in root.rglob('*') if path.is_file()}
    main([*arguments, '--check'], out=io.StringIO())
    assert before == {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in root.rglob('*') if path.is_file()}
    text = (root / 'sv/native_handles.sv').read_text(encoding='utf-8')
    assert 'SVXNativeRecords' in text
    assert 'typedef SVXNativeValueType_0 SVXValue_' in text
    assert 'type(value.' not in text
    assert 'import scoped_nominal_bus_types_pkg::*;' not in text
    assert 'scoped_nominal_bus_types_pkg::' not in text
    assert 'this.value.exchange_nominal(' in text
    assert 'this.value.echo_modes(' in text
    manifest = json.loads((root / 'inheritance.json').read_text(encoding='utf-8'))
    assert {item['symbol'] for item in manifest['value_types']} >= {
        'scoped_nominal_bus_types_pkg::Mode', 'scoped_nominal_bus_types_pkg::Payload'}
