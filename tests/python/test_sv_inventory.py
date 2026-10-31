import io
import json

import pytest

from svx.cli import main
from svx.errors import SVXInheritanceError

pytest.importorskip('pyslang')


def inspect(source, *options):
    output = io.StringIO()
    assert main(['inspect', '--sv-source', str(source), '--json', *options], out=output) == 0
    return json.loads(output.getvalue())


def test_inventory_reports_lexical_owners_without_claiming_instance_export(tmp_path):
    source = tmp_path / 'owners.sv'
    source.write_text('''class UnitClass;
class Nested;endclass
endclass
package p;
class Outer;
typedef bit[7:0] Word;
class Inner;endclass
function int method();typedef int LocalOnly;return 1;endfunction
task method_task();typedef int TaskLocalOnly;endtask
endclass
endpackage
module m;
class LocalClass;endclass
if (1) begin:selected
class Generated;endclass
end else begin:not_selected
class Other;endclass
end
for(genvar i=0;i<2;i++)begin:lanes
class Lane;endclass
end
endmodule
interface bus_if;class LocalClass;endclass endinterface
program test_program;class LocalClass;endclass endprogram
''', encoding='utf-8')
    data = inspect(source)
    assert data['analysis'] == 'preprocessed-declarations'
    assert data['elaborated_instances'] is False
    items = {item['symbol']: item for item in data['declarations']}
    assert set(items) == {'$unit::UnitClass', '$unit::UnitClass::Nested', 'p',
        'p::Outer', 'p::Outer::Word', 'p::Outer::Inner', 'm.LocalClass',
        'm.selected.Generated', 'm.not_selected.Other', 'm.lanes.Lane',
        'bus_if.LocalClass', 'test_program.LocalClass'}
    assert items['p::Outer::Inner']['export_status'] == 'selectable'
    assert items['$unit::UnitClass']['export_status'] == 'selectable'
    assert items['m.LocalClass']['export_status'] == 'requires-instance'
    assert items['bus_if.LocalClass']['export_status'] == 'requires-instance'
    assert [scope['kind'] for scope in items['m.lanes.Lane']['scope']] == [
        'compilation_unit', 'module', 'generate']
    assert items['m.not_selected.Other']['export_status'] == 'requires-instance'
    assert items['m.lanes.Lane']['export_status'] == 'requires-instance'
    assert items['bus_if.LocalClass']['scope'][1]['kind'] == 'interface'
    assert items['test_program.LocalClass']['scope'][1]['kind'] == 'program'
    assert data['compilation_units'] == [str(source.resolve())]
    assert data['dependencies'] == [str(source.resolve())]


def test_inventory_constants_tasks_imports_and_filters(tmp_path):
    source = tmp_path / 'values.sv'
    source.write_text('''package dep;class Base;endclass endpackage
package p;
import dep::*;
typedef enum bit[3:0] {IDLE=0, BUSY=5} Mode;
parameter int N=4, M=5;
function int get();typedef int LocalOnly;return N;endfunction
task tick();typedef int LocalTaskOnly;#1;endtask
class A;local typedef int Hidden;protected typedef int Protected;
typedef int Public;localparam int CLASS_N=7;endclass
endpackage''', encoding='utf-8')
    data = inspect(source)
    items = {item['symbol']: item for item in data['declarations']}
    assert items['p']['imports'] == ['dep']
    assert items['p::tick']['kind'] == 'callable'
    assert items['p::get']['kind'] == 'callable'
    assert items['p::N']['kind'] == items['p::M']['kind'] == 'constant'
    assert items['p::A::Hidden']['export_status'] == 'not-public'
    assert items['p::A::Protected']['export_status'] == 'not-public'
    assert items['p::A::Public']['export_status'] == 'selectable'
    assert items['p::A::CLASS_N']['export_status'] == 'member-only'
    assert not any('LocalOnly' in name or 'LocalTaskOnly' in name for name in items)
    selected = inspect(source, '--kind', 'callable', 'constant', '--name', 'p::*')
    assert {item['symbol'] for item in selected['declarations']} == {
        'p::tick', 'p::get', 'p::N', 'p::M', 'p::A::CLASS_N'}
    assert {item['symbol'] for item in inspect(source, '--name', 'Base')['declarations']} == {'dep::Base'}


def test_inventory_distinguishes_unit_snapshots_from_runtime_signatures(tmp_path):
    source = tmp_path / 'unit_values.sv'
    source.write_text('typedef enum bit[1:0]{ON=1} RootMode;'
                      'class Driver;typedef enum bit[1:0]{OFF=0} Mode;endclass', encoding='utf-8')
    items = {item['symbol']: item for item in inspect(source)['declarations']}
    assert items['$unit::RootMode']['export_status'] == 'selectable'
    assert 'same-unit root nominal runtime types are supported' in items['$unit::RootMode']['reason']
    assert items['$unit::Driver::Mode']['export_status'] == 'selectable'
    assert 'type snapshots and same-unit nominal runtime signatures are supported' in items['$unit::Driver::Mode']['reason']


def test_inventory_reuses_original_filelist_macros_and_includes_readonly(tmp_path):
    include = tmp_path / 'inc'
    include.mkdir()
    header = include / 'api.svh'
    header.write_text('''`ifdef ENABLE_API
class Enabled;endclass
`else
class Disabled;endclass
`endif
''', encoding='utf-8')
    source = tmp_path / 'project.sv'
    source.write_text('package p;\n`include "api.svh"\nendpackage\n', encoding='utf-8')
    filelist = tmp_path / 'design.f'
    filelist.write_text('+define+ENABLE_API\n+incdir+inc\nproject.sv\n', encoding='utf-8')
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in tmp_path.rglob('*') if path.is_file()}
    output = io.StringIO()
    assert main(['inspect', '-f', str(filelist), '--sv-build-directory', str(tmp_path),
                 '--json'], out=output) == 0
    data = json.loads(output.getvalue())
    assert {item['symbol'] for item in data['declarations']} == {'p', 'p::Enabled'}
    enabled = data['declarations'][1]
    assert enabled['location']['file'] == str(header)
    assert enabled['location']['line'] == 2
    assert enabled['compilation_unit'] == str(source)
    assert set(data['dependencies']) == {str(header), str(source)}
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in tmp_path.rglob('*') if path.is_file()}


def test_inventory_preserves_independent_unit_identity(tmp_path):
    first, second = tmp_path / 'one.sv', tmp_path / 'two.sv'
    first.write_text('class A;endclass\n', encoding='utf-8')
    second.write_text('class A;endclass\n', encoding='utf-8')
    data = inspect(first, '--sv-source', str(second))
    assert [item['symbol'] for item in data['declarations']] == ['$unit::A', '$unit::A']
    assert {item['compilation_unit'] for item in data['declarations']} == {str(first), str(second)}
    assert set(data['compilation_units']) == {str(first), str(second)}


def test_shared_unit_has_one_owner_and_inventory_does_not_elaborate(tmp_path, monkeypatch):
    import svx.sv_scan as scanner

    first, second = tmp_path / 'one.sv', tmp_path / 'two.sv'
    first.write_text('`define API_NAME A\n', encoding='utf-8')
    second.write_text('class `API_NAME;endclass\nmodule dut;MissingModule x();endmodule', encoding='utf-8')
    calls = []
    original = scanner._parse_source_batch

    def counted(*args, **kwargs):
        calls.append(True)
        yield from original(*args, **kwargs)

    monkeypatch.setattr(scanner, '_parse_source_batch', counted)
    monkeypatch.setattr(scanner, 'elaborate_sources', lambda *args, **kwargs: pytest.fail('inventory elaborated'))
    data = inspect(first, '--sv-source', str(second), '--sv-compilation-unit', '--kind', 'class')
    assert data['compilation_units'] == [str(first)]
    assert [item['symbol'] for item in data['declarations']] == ['$unit::A']
    assert calls == [True]


def test_inventory_text_and_empty_filters(tmp_path):
    source = tmp_path / 'project.sv'
    source.write_text('class A;endclass', encoding='utf-8')
    output = io.StringIO()
    assert main(['inspect', '--sv-source', str(source)], out=output) == 0
    assert '$unit::A [selectable]' in output.getvalue()
    assert 'not elaborated instance paths' in output.getvalue()
    assert inspect(source, '--name', 'NoSuchName')['declarations'] == []


def test_inventory_physical_locations_survive_line_directives(tmp_path):
    source = tmp_path / 'project.sv'
    source.write_text('`line 900 "logical_alias.sv" 0\npackage p;\nclass A;endclass\nendpackage\n',
                      encoding='utf-8')
    items = {item['symbol']: item for item in inspect(source)['declarations']}
    assert items['p::A']['location'] == {'file': str(source), 'line': 3, 'column': 1}


def test_inventory_anonymous_generate_blocks_are_not_invented_instance_paths(tmp_path):
    source = tmp_path / 'project.sv'
    source.write_text('module top;\nif (1) begin\nclass A;endclass\nend\nendmodule', encoding='utf-8')
    item, = inspect(source)['declarations']
    assert item['scope'][-1] == {'kind': 'generate', 'name': '<anonymous@2:8>'}
    assert item['symbol'] == 'top.<anonymous@2:8>.A'
    assert item['export_status'] == 'requires-instance'


def test_inventory_requires_input():
    with pytest.raises(SVXInheritanceError, match='requires --sv-source'):
        main(['inspect'], out=io.StringIO())
