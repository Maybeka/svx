import ast
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import pytest

from svx.cli import main
from svx.declarations import enrich_virtual_interface_manifest, manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'functions.sv'
    path.write_text('''package helpers;
  function automatic int adjust(int value); return value+1; endfunction
endpackage
package calc;
  import helpers::*;
  typedef enum bit[3:0] {IDLE=0, ACTIVE=5} Mode;
  typedef struct packed {bit[7:0] tag; logic[3:0] flags; Mode mode;} Packet;
  int counter=0;
  function automatic int add(int left, int right, output int previous);
    previous=counter; counter++; return adjust(left+right);
  endfunction
  task automatic step(input int amount, output int previous, inout int total);
    #3ns; previous=counter; counter+=amount; total+=counter;
  endtask
  function automatic Packet echo(Packet value); return value; endfunction
  function automatic void clear(); counter=0; endfunction
  class Item;
    int tag;
    function new(int value); tag=value; endfunction
  endclass
  function automatic Item make_item(int tag); Item value=new(tag);return value;endfunction
  function automatic int item_tag(Item value); return value.tag;endfunction
endpackage''', encoding='utf-8')
    return path


def test_callable_only_manifest_preserves_all_formals(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_callable_targets=['add', 'step'])
    assert not manifest.classes and not manifest.value_types
    assert manifest.schema_version == '2.3.0'
    assert [item.symbol for item in manifest.callables] == ['calc::add', 'calc::step']
    step = manifest.callables[1].method
    assert [item.direction for item in step.parameters] == ['input', 'output', 'inout']
    data = manifest_dict(manifest)
    assert manifest_dict(parse_manifest(data)) == data
    generated = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/calc.py')]
    tree = ast.parse(generated)
    functions = {item.name: item for item in tree.body if isinstance(item, ast.FunctionDef)}
    assert [item.arg for item in functions['step'].args.args] == ['amount', 'previous', 'total']
    assert not any(isinstance(item, ast.ClassDef) for item in tree.body)
    sv = emit_sv_mirrors(manifest)
    assert 'calc::add(' in sv and 'calc::step(' in sv
    assert 'svpkg://calc' in sv and 'extends calc' not in sv


def test_package_selects_own_functions_not_imports(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_package_targets=['calc'])
    assert len(manifest.callables) == 6
    assert all(item.package == 'calc' for item in manifest.callables)
    recursive = manifest_from_declarations(sv_source_files=[source], sv_package_targets=['calc'],
                                           sv_recursive_packages=True)
    assert 'helpers::adjust' in {item.symbol for item in recursive.callables}


def test_callable_values_generate_named_dependencies(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_callable_targets=['echo'])
    assert not manifest.classes
    assert {item.symbol for item in manifest.value_types} == {'calc::Mode', 'calc::Packet'}
    source_text = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/calc.py')]
    assert source_text.index('from _svx_value_types.calc import') < source_text.index('def echo(')
    assert 'SVXValue_4_calc_Packet' in emit_sv_mirrors(manifest)


def test_unselected_class_handles_remain_opaque(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_callable_targets=['make_item', 'item_tag'])
    assert not manifest.classes
    returns = next(item.method for item in manifest.callables if item.name == 'make_item')
    assert returns.return_handle.target_type_name == 'sv://calc/Item'
    text = emit_sv_mirrors(manifest)
    assert 'calc::Item' in text and 'svx_external_handles_pkg' in text


def test_cli_reports_imports_and_checks_outputs(source, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--callable', 'calc::*', '--sv-source', str(source), '--out', str(output)]
    stream = io.StringIO()
    assert main(args, out=stream) == 0
    assert 'from svx_mirror.calc import step' in stream.getvalue()
    assert main(args + ['--check'], out=io.StringIO()) == 0
    artifacts = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['classes'] == [] and artifacts['generated_types'] == []
    assert len(artifacts['callables']) == 6
    assert artifacts['constructors'] == []


def test_generated_function_calls_existing_static_transport(source, tmp_path):
    output = tmp_path / 'generated'
    assert main(['export', '--callable', 'add', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(output / 'python'), str(Path(__file__).resolve().parents[2] / 'python'),
        str(Path(__file__).resolve().parents[3] / 'svtypes/python')]))
    result = subprocess.run([sys.executable, '-B', '-c', '''import svx.inheritance as bridge
calls=[]
bridge.invoke_sv_static=lambda *args: calls.append(args) or 42
from svx_mirror.calc import add
holder=object()
assert add(1,2,holder) == 42
assert calls == [('svpkg://calc', 'svpkg://calc#add', {'left':1,'right':2,'previous':holder})]
'''], env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_callable_exclusions_and_empty_selection(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_callable_targets=['calc::*'],
                                          sv_exclude_callables=['make_item', 'item_tag'])
    assert len(manifest.callables) == 4
    with pytest.raises(SVXInheritanceError, match='selection is empty'):
        manifest_from_declarations(sv_source_files=[source], sv_callable_targets=['add'],
                                   sv_exclude_callables=['*'])
    with pytest.raises(SVXInheritanceError, match='matched no package function/task'):
        manifest_from_declarations(sv_source_files=[source], sv_callable_targets=['Missing'])


def test_ambiguous_short_function_requires_package(tmp_path):
    path = tmp_path / 'ambiguous.sv'
    path.write_text('package a;function int f();return 1;endfunction endpackage\n'
                    'package b;function int f();return 2;endfunction endpackage', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='ambiguous SV callable.*a::f, b::f'):
        manifest_from_declarations(sv_source_files=[path], sv_callable_targets=['f'])


@pytest.mark.parametrize('direction', ['ref', 'const ref'])
def test_ref_is_rejected_before_publication(tmp_path, direction):
    path = tmp_path / 'ref.sv'
    path.write_text(f'package p;function void f({direction} int value);endfunction endpackage', encoding='utf-8')
    output = tmp_path / 'generated'
    with pytest.raises(SVXInheritanceError, match='unsupported ref'):
        main(['export', '--callable', 'f', '--sv-source', str(path), '--out', str(output)], out=io.StringIO())
    assert not output.exists()


def test_callable_vif_dependencies_enrich_without_class_target(tmp_path):
    path = tmp_path / 'interface.sv'
    path.write_text('''interface bus_if;
  bit ready;
  modport view(input ready);
endinterface
package p;
  function automatic virtual bus_if.view echo(virtual bus_if.view value);
    return value;
  endfunction
endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[path], sv_callable_targets=['echo'])
    method = manifest.callables[0].method
    assert method.parameters[0].handle.kind == 'virtual_interface'
    assert method.return_handle.operations[0].sv_member_name == 'ready'
    generated = emit_python_mirrors(manifest)
    assert any('svx_vif' in str(name) for name in generated)
    data = manifest_dict(manifest)
    del data['callables'][0]['method']['parameters'][0]['handle']['operations']
    del data['callables'][0]['method']['return_handle']['operations']
    raw = parse_manifest(data)
    assert not raw.callables[0].method.return_handle.operations
    enriched = enrich_virtual_interface_manifest(raw, sv_source_files=[path])
    assert enriched.callables[0].method.return_handle.operations


def test_callable_aliases_do_not_shadow_user_formals(tmp_path):
    path = tmp_path / 'names.sv'
    path.write_text('''package p;
  function int echo(int _svx_invoke_package, int _svx_register_package_contract);
    return _svx_invoke_package+_svx_register_package_contract;
  endfunction
endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[path], sv_callable_targets=['echo'])
    generated = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/p.py')]
    tree = ast.parse(generated)
    invoke = next(alias.asname for node in tree.body if isinstance(node, ast.ImportFrom)
                  for alias in node.names if alias.name == 'invoke_sv_static')
    assert invoke not in {'_svx_invoke_package', '_svx_register_package_contract'}
    assert 'def echo(_svx_invoke_package, _svx_register_package_contract):' in generated


def test_python_keyword_names_reject_before_generation(tmp_path):
    path = tmp_path / 'keyword.sv'
    path.write_text('package p; function int lambda(int value);return value;endfunction endpackage', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='incompatible with Python syntax'):
        manifest_from_declarations(sv_source_files=[path], sv_callable_targets=['lambda'])


def test_mixed_module_support_imports_are_not_overwritten(tmp_path):
    path = tmp_path / 'mixed_names.sv'
    path.write_text('''package p;
  class Driver; function int status(); return 1; endfunction endclass
  function int invoke_sv(int value);return value;endfunction
endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[path], sv_package_targets=['p'])
    generated = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/p.py')]
    assert 'invoke_sv as _svx_package_support_invoke_sv' in generated
    tree = ast.parse(generated)
    driver = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Driver')
    status = next(node for node in driver.body if isinstance(node, ast.FunctionDef) and node.name == 'status')
    assert any(isinstance(node, ast.Name) and node.id == '_svx_package_support_invoke_sv'
               for node in ast.walk(status))
    assert any(isinstance(node, ast.FunctionDef) and node.name == 'invoke_sv' for node in tree.body)


def test_support_rewrite_respects_locals_defaults_closures_and_comments():
    from svx.package_exports import _isolate_support_names

    source = '''from __future__ import annotations
# Preserve comments and string identities, not just executable behavior.
from svx.inheritance import invoke_sv
class View:
    def local(self, invoke_sv):
        return invoke_sv
    def global_call(self):
        return invoke_sv(1)
    def alias_parameter(self, _svx_package_support_invoke_sv):
        return invoke_sv(_svx_package_support_invoke_sv)
    def default(self, value=invoke_sv):
        return value(2)
    def nested(self):
        return (lambda invoke_sv: invoke_sv)(3), (lambda: invoke_sv(4))()
    def built_in(self):
        return len([1, 2])
marker = 'invoke_sv'
'''
    rewritten = _isolate_support_names(source, ['invoke_sv', 'len'])
    assert '# Preserve comments' in rewritten and "marker = 'invoke_sv'" in rewritten
    namespace = {}
    from svx import inheritance
    original = inheritance.invoke_sv
    try:
        inheritance.invoke_sv = lambda value: value+10
        exec(compile(rewritten, '<test>', 'exec'), namespace)
    finally:
        inheritance.invoke_sv = original
    namespace.update(invoke_sv=lambda value: -1, len=lambda value: -2)
    view = namespace['View']()
    assert view.local(8) == 8 and view.global_call() == 11 and view.default() == 12
    assert view.alias_parameter(5) == 15
    assert view.nested() == (3, 14) and view.built_in() == 2
