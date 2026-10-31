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
def project(tmp_path):
    source = tmp_path / 'design.sv'
    source.write_text('''module owner#(parameter int WIDTH=8);
class Base;
int count;
function new(int seed);count=seed;endfunction
virtual function int status();return count;endfunction
endclass
class Driver extends Base;
bit[WIDTH-1:0] mask;
function new(int seed);super.new(seed);endfunction
function void write_mask(input bit[WIDTH-1:0] value);mask=value;endfunction
static function int twice(int value);return value*2;endfunction
endclass
class Outer;class Inner;int value;endclass endclass
endmodule
module tb;owner#(8) a();owner#(13) b();endmodule''', encoding='utf-8')
    filelist = tmp_path / 'project.f'
    filelist.write_text('design.sv\n', encoding='utf-8')
    return source, filelist


def export(project, output, *selectors, extra=()):
    source, filelist = project
    args = ['export', '--class', *selectors, '-f', str(filelist),
            '--sv-build-directory', str(source.parent), '--out', str(output), *extra]
    messages = io.StringIO()
    assert main(args, out=messages) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    return json.loads((output / 'inheritance.json').read_text(encoding='utf-8')), messages.getvalue()


def test_instance_cli_discovers_real_type_lineage_and_uses_original_filelist(project, tmp_path):
    before = project[0].read_bytes()
    output = tmp_path / 'generated'
    data, messages = export(project, output, 'tb.a.Driver')
    assert data['schema_version'] == '2.6.0'
    source, = data['classes']
    assert source['symbol'] == 'Driver' and source['canonical_id'] == 'sv://instance/tb/a/class/Driver'
    assert source['source_scope'] == {'kind': 'instance', 'path': 'tb.a', 'container': 'module'}
    assert [base['canonical_id'] for base in source['base_lineage']] == ['sv://instance/tb/a/class/Base']
    assert source['fields'][0]['type']['sv'].replace(' ', '') == 'bit[7:0]'
    assert 'from svx_mirror_instance.tb.a.classes import Driver' in messages
    assert project[0].read_bytes() == before
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['instance_bindings'][0]['instance_path'] == 'tb.a'
    assert len(artifact['generated_types']) == 1
    subprocess_import(output, "from svx_mirror_instance.tb.a.classes import Driver\nassert Driver.__svx_foreign_class_id__=='sv://instance/tb/a/class/Driver'\n")


def test_instance_selection_preserves_distinct_parameterized_owners(project, tmp_path):
    data, _ = export(project, tmp_path / 'generated', 'tb.*.Driver')
    assert len(data['classes']) == 2
    widths = {source['source_scope']['path']: source['fields'][0]['type']['sv'].replace(' ', '')
              for source in data['classes']}
    assert widths == {'tb.a': 'bit[7:0]', 'tb.b': 'bit[12:0]'}


def test_instance_short_name_ambiguity_reports_actual_paths(project):
    with pytest.raises(SVXInheritanceError, match=r'ambiguous SV class.*tb.a.Driver.*tb.b.Driver'):
        manifest_from_declarations(sv_source_files=[project[0]], sv_class_targets=['Driver'])


def test_instance_exclusion_and_canonical_selection(project, tmp_path):
    data, _ = export(project, tmp_path / 'excluded', 'tb.*.Driver', extra=('--exclude-class', 'tb.b.Driver'))
    assert [source['source_scope']['path'] for source in data['classes']] == ['tb.a']
    data, _ = export(project, tmp_path / 'canonical', 'sv://instance/tb/b/class/Driver')
    assert [source['source_scope']['path'] for source in data['classes']] == ['tb.b']


def test_instance_nested_classes_do_not_generate_outer(project, tmp_path):
    output = tmp_path / 'nested'
    data, messages = export(project, output, 'tb.a.Outer::Inner')
    assert [source['symbol'] for source in data['classes']] == ['Outer::Inner']
    assert 'Type: svx_mirror_instance.tb.a.classes.Outer.Inner' in messages
    subprocess_import(output, '''from types import SimpleNamespace
from svx_mirror_instance.tb.a.classes import Outer
assert isinstance(Outer,SimpleNamespace)
assert Outer.Inner.__qualname__=='Outer.Inner'
''')


def test_instance_probe_checks_changed_native_signature(project):
    manifest = manifest_from_declarations(sv_source_files=[project[0]], sv_class_targets=['tb.b.Driver'])
    data = manifest_dict(manifest)
    data['classes'][0]['fields'][0]['type']['sv'] = 'int'
    with pytest.raises(SVXInheritanceError, match='does not match source type'):
        validate_sv_declarations(data['classes'], [project[0]])


def test_instance_static_ancestor_is_registered_once_even_if_also_selected(project):
    from svx.instance_exports import emit_instance_export_bridges
    source, _ = project
    source.write_text(source.read_text(encoding='utf-8').replace(
        'virtual function int status()', 'static function int base_twice(int value);return value*2;endfunction\nvirtual function int status()'), encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['tb.a.Base', 'tb.a.Driver'])
    text = emit_instance_export_bridges(manifest)
    assert text.count('register_static("sv://instance/tb/a/class/Base"') == 1
    assert text.count('register_static("sv://instance/tb/a/class/Driver"') == 1


def test_interface_cli_inserts_static_gateway_at_native_included_owner(tmp_path):
    definitions = tmp_path / 'owner.svh'
    definitions.write_text('''// 中文注释验证字节偏移
interface owner;
int state;
class Driver;
protected static function int sample();return state;endfunction
endclass
endinterface : owner
''', encoding='utf-8')
    top = tmp_path / 'top.sv'
    top.write_text('`include "owner.svh"\nmodule tb;owner a(),b();endmodule\n', encoding='utf-8')
    before = definitions.read_bytes()
    output = tmp_path / 'generated'
    assert main(['export', '--class', 'tb.*.Driver', '--sv-source', str(top),
                 '--sv-include-dir', str(tmp_path), '--out', str(output)], out=io.StringIO()) == 0
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    copied = '\n'.join((output/path).read_text(encoding='utf-8') for path in artifact['systemverilog_compile_order'])
    assert copied.index('class StaticGateway_0 extends Driver') < copied.index('endinterface : owner')
    assert copied.count('Driver::sample(') == 4
    assert 'SVXSourceType::sample(' not in copied
    assert all('initialize_owner(' + json.dumps(binding['static_initialization_key']) + ')' in copied
               for binding in artifact['instance_bindings'])
    assert definitions.read_bytes() == before


def test_interface_static_specialization_uses_actual_owner_scalar_parameters(tmp_path):
    source = tmp_path / 'design.sv'
    source.write_text('''interface owner#(parameter int WIDTH=8,parameter string LABEL="a",parameter logic[3:0] FLAGS=4'bx01z);
class Driver;
static function bit[WIDTH-1:0] echo(input bit[WIDTH-1:0] value);return value;endfunction
endclass
endinterface
module tb;owner#(8,"left") a();owner#(13,"right") b();endmodule
''', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'tb.*.Driver', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    copied = (output/artifact['systemverilog_compile_order'][0]).read_text(encoding='utf-8')
    assert '(WIDTH === 8)' in copied and '(WIDTH === 13)' in copied
    assert '(LABEL == "left")' in copied and '(LABEL == "right")' in copied
    assert "(FLAGS === 4'bx01z)" in copied


def test_interface_static_type_parameter_placement_has_explicit_pending_diagnostic(tmp_path):
    source = tmp_path / 'design.sv'
    source.write_text('''interface owner#(parameter type T=int);
class Driver;static function int sample();return 1;endfunction endclass
endinterface module tb;owner a();endmodule
''', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='owner type parameters remains unfinished'):
        main(['export', '--class', 'tb.a.Driver', '--sv-source', str(source),
              '--out', str(tmp_path/'generated')], out=io.StringIO())


def test_package_only_mode_does_not_silently_guess_an_instance(project, tmp_path):
    with pytest.raises(SVXInheritanceError, match='hierarchy elaboration'):
        export(project, tmp_path / 'generated', 'tb.a.Driver', extra=('--sv-elaboration', 'packages'))


def test_original_top_selection_controls_instance_discovery(project, tmp_path):
    source, _ = project
    source.write_text(source.read_text(encoding='utf-8') + '\nmodule unused;owner extra();endmodule\n', encoding='utf-8')
    command = tmp_path / 'compile.json'
    command.write_text(json.dumps({'directory': str(tmp_path),
        'arguments': ['compiler', '-top', 'tb', str(source)]}), encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--class', '*.Driver', '--sv-build-command', str(command),
                 '--exclude-class', 'tb.b.Driver', '--out', str(output)], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert [source['source_scope']['path'] for source in data['classes']] == ['tb.a']
    evidence = json.loads((output / 'inheritance.json.svx-discovery.json').read_text(encoding='utf-8'))
    assert evidence['configuration']['sv_build']['configuration']['top_modules'] == ['tb']


def test_instance_array_path_is_literal_and_preserves_evaluated_owner(tmp_path):
    source = tmp_path / 'array.sv'
    source.write_text('''module owner#(parameter int WIDTH=8);
class Driver;bit[WIDTH-1:0] mask;endclass endmodule
module tb;for(genvar i=0;i<2;i++)begin:lanes owner#(8+i) u();end endmodule''', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'tb.lanes[1].u.Driver', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    target, = data['classes']
    assert target['source_scope']['path'] == 'tb.lanes[1].u'
    assert target['fields'][0]['type']['sv'].replace(' ', '') == 'bit[8:0]'
    subprocess_import(output, '''from svx_mirror_instance.tb.svx_scope_5_lanes_p1.u.classes import Driver
assert Driver.__name__=='Driver'
''')
    wildcard = tmp_path / 'wildcard'
    assert main(['export', '--class', 'tb.lanes[*].u.Driver', '--sv-source', str(source),
                 '--out', str(wildcard)], out=io.StringIO()) == 0
    values = json.loads((wildcard / 'inheritance.json').read_text(encoding='utf-8'))
    assert {item['source_scope']['path'] for item in values['classes']} == {'tb.lanes[0].u', 'tb.lanes[1].u'}


def test_instance_closed_generic_ancestor_keeps_its_actual_specialization(tmp_path):
    source = tmp_path / 'generic.sv'
    source.write_text('''module owner;
class Width#(int W=4);bit[W-1:0] mask;endclass
class Driver extends Width#(13);endclass
endmodule module tb;owner a();endmodule''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--class', 'tb.a.Driver', '--sv-source', str(source),
                 '--out', str(output)], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    base, = data['classes'][0]['base_lineage']
    assert base['specialization']['arguments'][0]['value'] == 13
    assert base['fields'][0]['type']['sv'].replace(' ', '') == 'bit[12:0]'


def test_instance_context_is_command_scoped_and_collects_original_syntax_once(project):
    from svx.sv_frontend import source_analysis
    from svx.sv_instance_scan import _instances
    with source_analysis() as analysis:
        manifest_from_declarations(sv_source_files=[project[0]], sv_class_targets=['tb.a.Driver', 'tb.b.Driver'])
    assert analysis.parse_batches == 1
    assert _instances.get() is None


def test_package_export_never_creates_instance_workspace(project, tmp_path, monkeypatch):
    import svx.sv_instance_scan as instances
    source, _ = project
    source.write_text(source.read_text(encoding='utf-8') + '\npackage p;class Api;int value;endclass endpackage\n', encoding='utf-8')
    monkeypatch.setattr(instances, 'prepare_instance_analysis', lambda *a, **k: pytest.fail('package export elaborated instance workspace'))
    output = tmp_path / 'package'
    assert main(['export', '--package', 'p', '--sv-elaboration', 'packages',
                 '--sv-source', str(source), '--out', str(output)], out=io.StringIO()) == 0


def test_exact_instance_selection_does_not_walk_unrelated_dut(project, monkeypatch):
    import svx.sv_instance_scan as instances
    source, _ = project
    source.write_text(source.read_text(encoding='utf-8').replace('owner#(8) a();', 'owner#(8) a();dut d();')
        + '\nmodule dut;for(genvar i=0;i<100;i++)begin:g owner other();end endmodule\n', encoding='utf-8')
    original = instances.prepare_instance_analysis
    observed = []
    def record(*args, **kwargs):
        result = original(*args, **kwargs)
        observed.append(result)
        return result
    monkeypatch.setattr(instances, 'prepare_instance_analysis', record)
    manifest_from_declarations(sv_source_files=[source], sv_class_targets=['tb.a.Driver'])
    assert observed
    assert {scope['path'] for scope in observed[0].scopes.values()} == {'tb.a'}


def test_unique_bare_instance_class_alias_needs_no_qualified_metadata(tmp_path):
    source = tmp_path / 'alias.sv'
    source.write_text('module owner;class Driver;int value;endclass typedef Driver Alias;endmodule '
                      'module tb;owner a();endmodule', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Alias'])
    target, = manifest.classes
    assert target.symbol == 'Alias' and target.source_scope['path'] == 'tb.a'


def test_instance_member_filter_uses_public_native_path(project, tmp_path):
    data, _ = export(project, tmp_path / 'filtered', 'tb.a.Driver',
                     extra=('--member', 'tb.a.Driver.write_mask', 'tb.a.Base.count'))
    target, = data['classes']
    assert [method['name'] for method in target['methods']] == ['write_mask']
    assert target.get('fields', []) == []
    assert [field['name'] for field in target['base_lineage'][0]['fields']] == ['count']
