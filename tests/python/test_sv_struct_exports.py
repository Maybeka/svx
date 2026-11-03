import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import svtypes

from svx.cli import main
from svx.struct_contract import CAPABILITY
from svx.value_exports import parse_value_exports, value_modules
from svx.inheritance import parse_manifest, _manifest_handle_bindings
from svx.errors import SVXInheritanceError

pytest.importorskip('pyslang')


def test_native_runtime_fixture_generation_only(tmp_path, monkeypatch):
    capabilities = svtypes.runtime_capabilities()
    monkeypatch.setattr(svtypes, 'runtime_capabilities', lambda: SimpleNamespace(
        provided=(*capabilities.provided, CAPABILITY)))
    source = Path(__file__).parents[1] / 'integration' / 'struct_kinds.sv'
    output = tmp_path / 'native-generated'
    arguments = ['export', '--package', 'struct_kinds_pkg', '--sv-source', str(source),
                 '--out', str(output)]
    assert main(arguments, out=io.StringIO()) == 0
    assert main([*arguments, '--check'], out=io.StringIO()) == 0
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    driver = next(item for item in manifest['classes'] if item['symbol'] == 'struct_kinds_pkg::Driver')
    assert {method['name'] for method in driver['methods']} == {
        'read', 'echo', 'exchange', 'echo_handles', 'read_handles', 'handles_match',
        'transform', 'invoke_transform', 'invoke_exchange'}
    native = (output / 'mirrors.sv').read_text(encoding='utf-8')
    native += '\n' + '\n'.join(path.read_text(encoding='utf-8') for path in (output / 'support').rglob('*.svh'))
    assert 'typedef struct_kinds_pkg::Data SVXValue_16_struct_kinds_pkg_Data_t;' in native
    if 'svtypes.generated-field-operations.v1' in capabilities.provided:
        assert 'static function string svtypes_format(input SVXValue_16_struct_kinds_pkg_Handles_t value);' in native
        assert 'static function void svtypes_apply_plusargs(ref SVXValue_16_struct_kinds_pkg_Handles_t value' in native
    assert 'this.value.item.object_number' not in native
    assert 'this.svx_return_value.item.object_number' not in native


def test_same_named_struct_packing_change_invalidates_export(tmp_path, monkeypatch):
    capabilities = svtypes.runtime_capabilities()
    monkeypatch.setattr(svtypes, 'runtime_capabilities', lambda: SimpleNamespace(
        provided=(*capabilities.provided, CAPABILITY)))
    source = tmp_path / 'packing.sv'
    output = tmp_path / 'packing-output'
    source.write_text('package packing; typedef struct packed { bit[7:0] value; } Data; endpackage\n')
    arguments = ['export', '--type', 'packing::Data', '--sv-source', str(source),
                 '--incremental', '--out', str(output)]
    assert main(arguments, out=io.StringIO()) == 0
    first = json.loads((output / 'inheritance.json').read_text())['value_types'][0]
    source.write_text('package packing; typedef struct { bit[7:0] value; } Data; endpackage\n')
    with pytest.raises((SVXInheritanceError, SystemExit), match='stale|changed|differs'):
        main([*arguments, '--check'], out=io.StringIO())
    assert main(arguments, out=io.StringIO()) == 0
    second = json.loads((output / 'inheritance.json').read_text())['value_types'][0]
    assert first['svtypes']['packed'] is True and second['svtypes']['packed'] is False
    assert first['schema'] != second['schema']


def test_native_handle_adapter_respects_field_operations_capability(monkeypatch):
    from svx.struct_contract import _native_handle_struct

    schema = {'fields': [{'name': 'item', 'type': {
        'kind': 'remote_ref', 'target_type_name': 'sv://p/Item'}}]}
    source = 'typedef struct { int item; } Sample_t;\nclass Sample_packer; endclass'
    provided = svtypes.runtime_capabilities().provided
    monkeypatch.setattr(svtypes, 'runtime_capabilities', lambda: SimpleNamespace(
        provided=tuple(cap for cap in provided if cap != 'svtypes.generated-field-operations.v1')))
    old = _native_handle_struct(source, 'Sample', 'p::Sample', schema, '')
    assert 'svtypes_format(' not in old and 'svtypes_apply_plusargs(' not in old
    monkeypatch.setattr(svtypes, 'runtime_capabilities', lambda: SimpleNamespace(
        provided=(*provided, 'svtypes.generated-field-operations.v1')))
    new = _native_handle_struct(source, 'Sample', 'p::Sample', schema, '')
    assert 'static function string svtypes_format(' in new
    assert 'static function void svtypes_apply_plusargs(' in new


@pytest.fixture
def struct_source(tmp_path):
    path = tmp_path / 'structs.sv'
    path.write_text('''package struct_export_pkg;
typedef struct packed { bit [7:0] tag; logic [3:0] flags; } Header;
typedef struct { Header header; string label; real gain;
                 int samples[2]; byte payload[$]; } Data;
typedef struct { int code; string label; } Meta;
localparam Meta DEFAULT_META='{code:17, label:"constant"};
class Item;
  int code;
  function new(); code=5; endfunction
endclass
typedef struct { Item item; Item same_item; } HandleData;
class Driver;
  Data data;
  HandleData handles;
  function new(); data.label="initial"; endfunction
  function Data echo(input Data value); return value; endfunction
  function HandleData echo_handles(input HandleData value); return value; endfunction
  task exchange(input Data value, output Data previous, inout Data current);
    #1ns; previous=current; current=value;
  endtask
endclass
endpackage
''', encoding='utf-8')
    return path


def test_source_struct_exports_with_development_capability_fixture(struct_source, tmp_path, monkeypatch):
    capabilities = svtypes.runtime_capabilities()
    monkeypatch.setattr(svtypes, 'runtime_capabilities', lambda: SimpleNamespace(
        provided=(*capabilities.provided, CAPABILITY)))
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'struct_export_pkg', '--sv-source', str(struct_source),
                 '--out', str(output)], out=io.StringIO()) == 0
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert CAPABILITY in manifest['required_runtime_capabilities']
    types = {item['symbol']: item for item in manifest['value_types']}
    assert types['struct_export_pkg::Header']['schema']['packed'] is True
    assert types['struct_export_pkg::Data']['schema']['packed'] is False
    assert types['struct_export_pkg::Data']['svtypes']['packed'] is False
    handles = types['struct_export_pkg::HandleData']['schema']['fields']
    assert [field['type']['kind'] for field in handles] == ['remote_ref', 'remote_ref']
    assert handles[0]['type']['target_type_name'] == 'sv://struct_export_pkg/Item'
    constant = next(item for item in manifest['constants'] if item['symbol'].endswith('::DEFAULT_META'))
    with value_modules(parse_value_exports(manifest['value_types'])):
        codec = svtypes.materialize_type_spec(svtypes.type_spec_from_identity(constant['svtypes']),
                                             location='DEFAULT_META')
        value, consumed = codec.unpack(bytes.fromhex(constant['data']))
    assert consumed == len(bytes.fromhex(constant['data']))
    assert value.code.value == 17 and value.label.value == 'constant'
    generated = '\n'.join(path.read_text(encoding='utf-8') for path in (output / 'python').rglob('*.py'))
    assert '.SvPackedStruct):' in generated
    assert '.SvStruct):' in generated
    assert 'require_runtime_compatible' in generated and CAPABILITY in generated
    manifest['required_runtime_capabilities'].remove(CAPABILITY)
    manifest.pop('discovery_provenance', None)
    with pytest.raises(SVXInheritanceError, match='missing required capabilities'):
        parse_manifest(manifest)
    manifest['required_runtime_capabilities'].append(CAPABILITY)
    parsed = parse_manifest(manifest)
    bindings = _manifest_handle_bindings(parsed)
    nested = [binding for binding in bindings if binding.target_type_name == 'sv://struct_export_pkg/Item']
    assert len(nested) == 1 and nested[0].sv_type == 'struct_export_pkg::Item'
