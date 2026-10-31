import io
import json

import pytest

from svx.cli import main
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.sv_scan import validate_sv_declarations
from test_sv_nested_classes import subprocess_import

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'design.sv'
    path.write_text('''module owner#(parameter int WIDTH=8);
int state;
for(genvar I=0;I<2;I++)begin:lanes
localparam int BITS=WIDTH+I;
class Base;
int count;
function new(int seed);count=seed;endfunction
virtual function int status();return state+count+I;endfunction
endclass
class Driver extends Base;
bit[BITS-1:0] mask;
function new(int seed);super.new(seed);endfunction
function void write_mask(input bit[BITS-1:0] value);mask=value;endfunction
static function int owner_index();return I;endfunction
endclass
end:lanes
endmodule
module tb;owner#(8) a(),b();owner#(13) c();endmodule
''', encoding='utf-8')
    return path


def export(source, output, *selectors):
    args = ['export', '--class', *selectors, '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    return (json.loads((output/'inheritance.json').read_text(encoding='utf-8')),
            json.loads((output/'artifacts.json').read_text(encoding='utf-8')))


def test_generate_cli_keeps_native_classes_and_evaluated_owner_types(source, tmp_path):
    before = source.read_bytes()
    output = tmp_path/'generated'
    data, artifact = export(source, output, 'tb.*.lanes[*].Driver')
    assert len(data['classes']) == 6
    widths = {item['source_scope']['path']: item['fields'][0]['type']['sv'].replace(' ', '') for item in data['classes']}
    assert widths['tb.a.lanes[0]'] == 'bit[7:0]'
    assert widths['tb.a.lanes[1]'] == 'bit[8:0]'
    assert widths['tb.c.lanes[1]'] == 'bit[13:0]'
    assert all(item['bridge_kind'] == 'generate' and 'bridge_module' not in item for item in artifact['instance_bindings'])
    copied = (output/artifact['systemverilog_compile_order'][0]).read_text(encoding='utf-8')
    assert 'extends Driver implements' in copied
    assert '(I === 0)' in copied and '(I === 1)' in copied
    assert '(WIDTH === 8)' in copied and '(WIDTH === 13)' in copied
    assert 'bind tb.a.lanes' not in copied
    assert source.read_bytes() == before
    subprocess_import(output, '''from svx_mirror_instance.tb.a.svx_scope_5_lanes_p1.classes import Driver
assert Driver.__svx_foreign_class_id__=='sv://instance/tb/a/svx_scope_5_lanes_p1/class/Driver'
''')


def test_generate_member_validation_rejects_wrong_field_type(source):
    data = manifest_dict(manifest_from_declarations(sv_source_files=[source], sv_class_targets=['tb.c.lanes[1].Driver']))
    data['classes'][0]['fields'][0]['type']['sv'] = 'int'
    with pytest.raises(SVXInheritanceError, match='does not match source type'):
        validate_sv_declarations(data['classes'], [source])


def test_nested_generate_parent_guards_precede_shadowing_child(source, tmp_path):
    text = source.read_text(encoding='utf-8')
    text = text.replace('class Base;', 'if(1)begin:inner_scope\nlocalparam int I=99;\nclass Base;')
    text = text.replace('end:lanes', 'end:inner_scope\nend:lanes')
    source.write_text(text, encoding='utf-8')
    output = tmp_path/'generated'
    _, artifact = export(source, output, 'tb.a.lanes[1].inner_scope.Driver')
    copied = (output/artifact['systemverilog_compile_order'][0]).read_text(encoding='utf-8')
    inner = copied.index('if(1)begin:inner_scope')
    assert copied.index('_scope_1 = ') < inner
    assert '(I === 1)' in copied[:inner]
    assert '(I === 99)' not in copied


def test_generate_class_from_independent_filelist_units_and_include(source, tmp_path):
    header = tmp_path/'owner.svh'
    header.write_text(source.read_text(encoding='utf-8').split('module tb;')[0], encoding='utf-8')
    source.write_text('`include "owner.svh"\n', encoding='utf-8')
    top = tmp_path/'top.sv'
    top.write_text('module tb;owner#(13) a();endmodule\n', encoding='utf-8')
    filelist = tmp_path/'project.f'
    filelist.write_text('+incdir+.\ndesign.sv\ntop.sv\n', encoding='utf-8')
    output = tmp_path/'generated'
    args = ['export', '--class', 'tb.a.lanes[1].Driver', '-f', str(filelist),
            '--sv-build-directory', str(tmp_path), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args+['--check'], out=io.StringIO()) == 0
    data = json.loads((output/'inheritance.json').read_text(encoding='utf-8'))
    assert data['classes'][0]['fields'][0]['type']['sv'].replace(' ', '') == 'bit[13:0]'


def test_anonymous_generate_scope_is_discovered_without_user_guessing(tmp_path):
    source = tmp_path/'design.sv'
    source.write_text('module tb;if(1)begin class Driver;int value;endclass end endmodule\n', encoding='utf-8')
    data, _ = export(source, tmp_path/'generated', 'Driver')
    assert data['classes'][0]['source_scope']['path'] == 'tb.genblk1'


def test_inactive_generate_branch_is_not_an_export_target(tmp_path):
    source = tmp_path/'design.sv'
    source.write_text('module tb;if(0)begin:absent class Driver;endclass end endmodule\n', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='matched no package, compilation-unit or instance class'):
        export(source, tmp_path/'generated', 'tb.absent.Driver')
