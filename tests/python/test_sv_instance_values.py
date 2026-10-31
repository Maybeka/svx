import importlib
import io
import json
import sys

import pytest

from svx.cli import main
from svx.declarations import manifest_from_declarations
from svx.declarations import manifest_dict
from svx.errors import SVXInheritanceError
from svx.source_scopes import instance_public_module

pytest.importorskip('pyslang')


@pytest.fixture
def design(tmp_path):
    source = tmp_path / 'values.sv'
    source.write_text('''module values #(int W=8);
typedef enum bit[W-1:0] {ZERO=W'(0), ONE=W'(1)} Mode;
typedef Mode Alias;
typedef struct packed {Mode mode;bit[W-1:0] data;} Payload;
typedef bit[W-1:0] Word;
typedef Payload Packets[2];
typedef Mode Modes[$];
localparam Mode DEFAULT_MODE=ONE;
localparam Payload DEFAULT_PAYLOAD={ONE,{W{1'b1}}};
class Holder;typedef enum bit[2:0] {SMALL=2} Tag;endclass
endmodule
module tb;
values a();values b();values#(13) c();
for(genvar i=0;i<2;i++)begin: lanes
typedef bit[i+2:0] Index;
localparam int ID=i;
end
endmodule
''', encoding='utf-8')
    return source


def test_instance_value_selection_has_independent_owner_identities(design):
    manifest = manifest_from_declarations(sv_source_files=[design],
        sv_type_targets=['tb.*.Mode', 'tb.*.Alias', 'tb.*.Payload', 'tb.*.Word', 'tb.a.Holder::Tag'],
        sv_constant_targets=['tb.*.W', 'tb.*.DEFAULT_MODE', 'tb.*.DEFAULT_PAYLOAD'])
    assert manifest.schema_version == '2.6.0'
    assert not manifest.classes
    entries = {item.key: item for item in manifest.value_types}
    for owner, width in [('tb.a', 8), ('tb.b', 8), ('tb.c', 13)]:
        mode = entries[f'$instance[{owner}]::Mode']
        assert mode.module == instance_public_module(owner)
        assert mode.as_dict()['schema']['width'] == width
        assert mode.source_scope == {'kind': 'instance', 'path': owner, 'container': 'module'}
        assert entries[f'$instance[{owner}]::Alias'].as_dict()['schema'] == mode.as_dict()['schema']
    assert entries['$instance[tb.a]::Mode'].as_dict()['schema']['type_name'] != entries['$instance[tb.b]::Mode'].as_dict()['schema']['type_name']
    assert entries['$instance[tb.a]::Holder::Tag'].qualname == 'Holder.Tag'


def test_instance_value_cli_generates_importable_types_and_snapshots(design, tmp_path, monkeypatch):
    output = tmp_path / 'generated'
    args = ['export', '--type', 'tb.*.Mode', 'tb.*.Alias', 'tb.*.Payload', 'tb.*.Word',
            'tb.*.Packets', 'tb.*.Modes',
            'tb.a.Holder::Tag', 'tb.lanes[*].Index', '--constant', 'tb.*.W',
            'tb.*.DEFAULT_MODE', 'tb.*.DEFAULT_PAYLOAD', 'tb.lanes[*].ID',
            '--sv-source', str(design), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert 'systemverilog_startup_module' not in artifact
    monkeypatch.syspath_prepend(str(output / 'python'))
    imported = []
    try:
        for owner, width in [('tb.a', 8), ('tb.b', 8), ('tb.c', 13)]:
            module = importlib.import_module(instance_public_module(owner))
            imported.append(module)
            assert module.Mode.__name__ == 'Mode'
            assert module.Mode.__module__ == instance_public_module(owner)
            assert module.Alias is module.Mode
            assert module.W == width and module.DEFAULT_MODE == module.Mode.ONE
            assert module.DEFAULT_PAYLOAD.mode.value == module.Mode.ONE
            assert module.DEFAULT_PAYLOAD.data.value == (1 << width)-1
            value = module.Payload()
            value.mode.value = module.Mode.ONE
            value.data.value = 5
            data = module.Payload().pack(value)
            decoded, consumed = module.Payload().unpack(data)
            assert consumed == len(data) and decoded.data.value == 5
            data = module.Packets().pack([value, value])
            decoded, consumed = module.Packets().unpack(data)
            assert consumed == len(data) and decoded[1].data.value == 5
            data = module.Modes().pack([module.Mode.ONE, module.Mode.ZERO])
            decoded, consumed = module.Modes().unpack(data)
            assert consumed == len(data) and decoded == [1, 0]
        assert imported[0].Mode is not imported[1].Mode
        assert imported[0].Holder.Tag.SMALL == 2
        for index in range(2):
            module = importlib.import_module(instance_public_module(f'tb.lanes[{index}]'))
            assert module.ID == index and module.Index().width == index+3
    finally:
        for name in tuple(sys.modules):
            if name.startswith(('svx_mirror_instance', '_svx_instance_value_types')):
                sys.modules.pop(name, None)


def test_instance_values_reject_ambiguous_short_names_and_package_only_mode(design):
    with pytest.raises(SVXInheritanceError, match='ambiguous SV type'):
        manifest_from_declarations(sv_source_files=[design], sv_type_targets=['Mode'])
    from svx.sv_frontend import source_elaboration
    with source_elaboration('packages'), pytest.raises(SVXInheritanceError, match='--sv-elaboration all'):
        manifest_from_declarations(sv_source_files=[design], sv_type_targets=['tb.a.Mode'])


def test_instance_value_exclusion_checks_required_dependencies(design):
    with pytest.raises(SVXInheritanceError, match='requires excluded SV value type'):
        manifest_from_declarations(sv_source_files=[design],
            sv_type_targets=['tb.a.Payload'], sv_exclude_types=['tb.a.Mode'])


@pytest.mark.parametrize('container', ['interface', 'program'])
def test_other_native_containers_use_the_same_value_contract(design, container):
    text = design.read_text(encoding='utf-8').replace('module values', container + ' values', 1)
    text = text.replace('endclass\nendmodule', 'endclass\nend' + container, 1)
    design.write_text(text, encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[design],
        sv_type_targets=['tb.*.Payload'], sv_constant_targets=['tb.*.DEFAULT_PAYLOAD'])
    assert {item.source_scope['container'] for item in manifest.value_types} == {container}


def test_instance_value_contract_rejects_invalid_scope_and_class_collisions(design):
    from svx.inheritance import parse_manifest
    from svx.source_scopes import instance_class_id

    manifest = manifest_from_declarations(sv_source_files=[design], sv_type_targets=['tb.a.Mode'])
    for scope in [{'kind': 'instance', 'path': ''},
                  {'kind': 'instance', 'path': 'tb.a', 'container': []},
                  {'kind': 'instance', 'path': 'tb.a', 'index': 0}]:
        data = manifest_dict(manifest)
        data['value_types'][0]['source_scope'] = scope
        with pytest.raises(SVXInheritanceError):
            parse_manifest(data)
    data = manifest_dict(manifest)
    data['classes'] = [{'canonical_id': instance_class_id('tb.a', 'Mode'), 'language': 'sv',
                        'symbol': 'Mode', 'source_scope': manifest.value_types[0].source_scope}]
    with pytest.raises(SVXInheritanceError, match='conflicting class, value type or constant'):
        parse_manifest(data)


def test_instance_value_inventory_reports_concrete_owner_requirement(design):
    output = io.StringIO()
    assert main(['inspect', '--sv-source', str(design), '--kind', 'type', 'constant', '--json'], out=output) == 0
    entries = json.loads(output.getvalue())['declarations']
    selected = {item['symbol']: item for item in entries
                if item['symbol'] in {'values.Mode', 'values.Payload', 'values.W'}}
    assert set(selected) == {'values.Mode', 'values.Payload', 'values.W'}
    assert all(item['export_status'] == 'requires-instance' for item in selected.values())


def test_instance_nominal_runtime_binding_rejects_cross_owner_scope(design):
    from svx.declarations import inheritance_parameter
    from svx.inheritance import parse_manifest
    from svx.source_scopes import instance_class_id
    from svx.value_exports import value_modules

    manifest = manifest_from_declarations(sv_source_files=[design], sv_type_targets=['tb.a.Mode'])
    value, = manifest.value_types
    with value_modules(manifest.value_types) as modules:
        binding = inheritance_parameter('mode', modules.annotations[value.key])['type']
    data = manifest_dict(manifest)
    data['classes'] = [{'canonical_id': instance_class_id('tb.b', 'Driver'), 'language': 'sv',
                        'symbol': 'Driver', 'source_scope': {**value.source_scope, 'path': 'tb.b'},
                        'fields': [{'name': 'mode', 'type': binding}]}]
    with pytest.raises(SVXInheritanceError, match='matching owner-local call records'):
        parse_manifest(data)


@pytest.mark.parametrize('container', ['module', 'interface', 'program'])
def test_class_only_export_collects_owner_local_runtime_value_types(design, tmp_path, container):
    text = design.read_text(encoding='utf-8').replace('endmodule\nmodule tb;', '''class Driver;
Mode mode;
Payload payload;
function new(Mode initial_mode);mode=initial_mode;endfunction
virtual function Mode echo(input Mode value);mode=value;return mode;endfunction
virtual function Payload echo_payload(input Payload value);payload=value;return payload;endfunction
function Modes echo_modes(input Modes values);return values;endfunction
virtual function Packets echo_packets(input Packets values);return values;endfunction
task advance(input Mode value,output Payload previous,inout Word count);
#1ns;previous=payload;mode=value;payload.mode=value;count+=1;
endtask
static function Mode static_echo(Mode value);return value;endfunction
endclass
endmodule
module tb;''')
    if container != 'module':
        text = text.replace('module values', container + ' values', 1)
        text = text.replace('endclass\nendmodule', 'endclass\nend' + container, 1)
    design.write_text(text, encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'tb.*.Driver', '--sv-source', str(design), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(data['classes']) == 3
    for owner in ('tb.a', 'tb.b', 'tb.c'):
        types = {value['symbol'] for value in data['value_types'] if value['source_scope']['path'] == owner}
        assert types >= {'Mode', 'Payload', 'Word', 'Modes', 'Packets'}
    from test_sv_nested_classes import subprocess_import
    subprocess_import(output, '''from svx_mirror_instance.tb.a.classes import Driver,Mode,Payload
from svx_mirror_instance.tb.b.classes import Mode as OtherMode
assert Mode is not OtherMode
value=Payload()
value.mode.value=Mode.ONE
assert value.mode.value==1
''')


def test_primitive_alias_only_class_signature_is_validated_in_its_native_owner(tmp_path):
    source = tmp_path / 'words.sv'
    source.write_text('''module owner #(int W=7);
typedef bit[W-1:0] Word;
typedef Word Words[$];
class Driver;
function Word echo(Word value);return value;endfunction
function Words echo_words(Words value);return value;endfunction
endclass
endmodule
module tb;owner a();endmodule
''', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'tb.a.Driver', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert {value['symbol'] for value in data['value_types']} == {'Word', 'Words'}
