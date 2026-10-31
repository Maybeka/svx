import io
import json

import pytest

from svx.cli import main
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import parse_manifest
from svx.inheritance import _call_record_class_name
from test_sv_nested_classes import subprocess_import

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'values.sv'
    path.write_text('''typedef enum bit[2:0]{IDLE=0,ACTIVE=5} Mode;
typedef struct packed{Mode mode;logic[3:0] flags;} Packet;
typedef Mode Modes[];
class Driver;
Packet packet;
function Mode echo(input Mode mode);return mode;endfunction
function Packet echo_packet(input Packet value);return value;endfunction
function Modes echo_modes(input Modes value);return value;endfunction
endclass''', encoding='utf-8')
    return path


def test_same_owner_enum_struct_and_container_runtime_bindings(source, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--class', 'Driver', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert {value['symbol'] for value in data['value_types']} >= {'$unit::Mode', '$unit::Packet'}
    text = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert 'typedef $unit::Mode SVXUnitValue_' in text
    assert 'import $unit::*' not in text
    assert text.index('typedef $unit::Mode SVXUnitValue_') < text.index('class SVXCall_')
    array_record = _call_record_class_name('sv://unit/0/Driver#echo_modes', 'request')
    body = text.split(f'class {array_record} extends', 1)[1].split('endclass', 1)[0]
    assert 'covergroup' not in body
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Driver,Mode,Packet
from svtypes import LogicValue
p=Packet()
p.mode.value=Mode.ACTIVE
p.flags.value=LogicValue.from_string('10xz')
assert p.mode.value==5 and p.flags.value==LogicValue.from_string('10xz')
''')


def test_named_runtime_values_do_not_cross_compilation_unit_owners(source, tmp_path):
    second = tmp_path / 'second.sv'
    second.write_text('typedef enum bit[2:0]{OTHER=1} Mode;', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source, second],
        sv_class_targets=['Driver'], sv_type_targets=['$unit::*'])
    data = manifest_dict(manifest)
    target = data['classes'][0]
    target['source_scope']['index'] = 1
    target['canonical_id'] = 'sv://unit/1/Driver'
    for method in target['methods']:
        method['canonical_id'] = target['canonical_id'] + '#' + method['name']
    with pytest.raises(SVXInheritanceError, match='matching owner-local call records'):
        parse_manifest(data)


def test_class_owned_unit_named_types_use_owner_local_records(tmp_path):
    path = tmp_path / 'nested_values.sv'
    path.write_text('''class Driver;
typedef enum bit[1:0]{ON=1} State;
typedef struct packed{State state;logic[3:0] flags;} Packet;
typedef State States[];
Packet packet;
function State echo(input State state);return state;endfunction
function Packet echo_packet(input Packet value);return value;endfunction
function States echo_states(input States value);return value;endfunction
endclass''', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'Driver', '--type', 'Driver::States',
            '--sv-source', str(path), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert {value['symbol'] for value in data['value_types']} >= {'$unit::Driver::State', '$unit::Driver::Packet'}
    text = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert 'typedef $unit::Driver::State SVXUnitValue_' in text
    assert 'import $unit::*' not in text
    enum_record = _call_record_class_name('sv://unit/0/Driver#echo', 'request')
    body = text.split(f'class {enum_record} extends', 1)[1].split('endclass', 1)[0]
    assert 'covergroup' not in body and '$value$plusargs' not in body
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Driver
from svtypes import LogicValue
packet=Driver.Packet()
packet.state.value=Driver.State.ON
packet.flags.value=LogicValue.from_string('10xz')
assert packet.state.value==1 and packet.flags.value==LogicValue.from_string('10xz')
states=Driver.States()
states.value=[Driver.State.ON]
assert states.value==[1]
assert Driver.State.__qualname__=='Driver.State'
''')


def test_class_and_value_export_cannot_overwrite_same_unit_public_name(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_type_targets=['$unit::Mode'])
    data = manifest_dict(manifest)
    data['classes'] = [{'canonical_id': 'sv://unit/0/Mode', 'language': 'sv', 'symbol': '$unit::Mode',
                        'source_scope': {'kind': 'compilation_unit', 'index': 0}, 'methods': []}]
    with pytest.raises(SVXInheritanceError, match='conflicting class, value type'):
        parse_manifest(data)


def test_same_class_and_value_name_in_distinct_units_is_legal(tmp_path):
    first, second = tmp_path / 'first.sv', tmp_path / 'second.sv'
    first.write_text('class Driver;endclass', encoding='utf-8')
    second.write_text('typedef enum bit[2:0]{ACTIVE=5} Driver;', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--class', 'Driver', '--type', '$unit[1]::Driver',
                 '--sv-source', str(first), '--sv-source', str(second), '--out', str(output)], out=io.StringIO()) == 0
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Driver
from svx_mirror_unit.unit_1 import Driver as Mode
assert Driver is not Mode and Mode.ACTIVE==5
assert Driver.__name__==Mode.__name__=='Driver'
''')


def test_unit_value_bindings_keep_explicit_scope_when_class_shadows_name(tmp_path):
    source = tmp_path / 'shadow.sv'
    source.write_text('''typedef enum bit[2:0]{ACTIVE=5} Mode;
class Driver;
typedef bit[7:0] Mode;
function $unit::Mode echo(input $unit::Mode value);return value;endfunction
endclass''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'])
    method, = manifest.classes[0].methods
    assert method.parameters[0].type_binding.sv == '$unit::Mode'
    assert method.return_type.sv == '$unit::Mode'


def test_class_owned_unit_value_selectors_disambiguate_and_exclude_by_owner(tmp_path):
    first, second = tmp_path / 'first.sv', tmp_path / 'second.sv'
    for path, value in ((first, 1), (second, 2)):
        path.write_text(f'class Driver;typedef enum bit[1:0]{{ON={value}}} State;endclass', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='ambiguous SV type'):
        manifest_from_declarations(sv_source_files=[first, second], sv_type_targets=['Driver::State'])
    output = tmp_path / 'generated'
    assert main(['export', '--type', 'Driver::*', '--exclude-type', '$unit[1]::Driver::State',
                 '--sv-source', str(first), '--sv-source', str(second), '--out', str(output)],
                out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(data['value_types']) == 1
    assert data['value_types'][0]['source_scope']['index'] == 0
    subprocess_import(output, 'from svx_mirror_unit.unit_0 import Driver\nassert Driver.State.ON==1\n')
    second_output = tmp_path / 'second-generated'
    assert main(['export', '--type', '$unit[1]::Driver::State',
                 '--sv-source', str(first), '--sv-source', str(second), '--out', str(second_output)],
                out=io.StringIO()) == 0
    subprocess_import(second_output, 'from svx_mirror_unit.unit_1 import Driver\nassert Driver.State.ON==2\n')
