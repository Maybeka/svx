import io
import json
from pathlib import Path

import pytest

from svx.cli import main

pytest.importorskip('pyslang')


BODY = (Path(__file__).resolve().parents[1] / 'integration/scoped_handle_types.sv').read_text(encoding='utf-8')


def test_unit_handle_dependencies_use_one_shared_native_type_adapter(tmp_path):
    source = tmp_path / 'handles.sv'
    source.write_text(BODY, encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'Owner', 'Consumer', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['systemverilog_compile_order'] == ['sv/native_handles.sv', 'sv/source.sv', 'sv/exports.sv']
    assert len(artifact['source_replacements']) == 1
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert {item['symbol'] for item in data['classes']} == {'$unit::Owner', '$unit::Consumer'}
    text = (output / 'sv/native_handles.sv').read_text(encoding='utf-8')
    assert 'package svx_scoped_handles_pkg;' in text
    assert ' #(type SVXNativeHandleType)' in text
    assert '$unit::Item' not in text
    assert 'svx_call_records_pkg' not in text
    source_text = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert 'svx_scoped_handles_pkg::SVXExternal_sv_c_s_sunit_s0_sItem#($unit::Item)::' in source_text


def test_local_scope_rejects_duplicate_generated_bridge_names():
    import pyslang
    from svx.errors import SVXInheritanceError
    from svx.source_scopes import native_scope_insertions
    compilation = pyslang.ast.Compilation()
    compilation.addSyntaxTree(pyslang.syntax.SyntaxTree.fromText('module owner;endmodule'))
    with pytest.raises(SVXInheritanceError, match='duplicate generated local bridge'):
        native_scope_insertions(compilation, {'owner': [
            {'name': 'helper', 'text': ''}, {'name': 'helper', 'text': ''}]})


@pytest.mark.parametrize('container', ['module', 'interface', 'program', 'generate'])
def test_instance_class_handles_keep_their_actual_owner_without_exporting_item(tmp_path, container):
    source = tmp_path / 'instances.sv'
    body = BODY
    native_container = 'module' if container == 'generate' else container
    if container == 'generate':
        body = 'for(genvar i=0;i<1;i++)begin: lane\n' + body + '\nend'
    source.write_text(native_container + ' owner #(int W=8);\n' + body + '\nend' + native_container
                      + '\nmodule tb;owner a(),b();owner#(13)c();endmodule', encoding='utf-8')
    prefix = 'tb.*.lane[0]' if container == 'generate' else 'tb.*'
    output = tmp_path / 'generated'
    args = ['export', '--class', prefix+'.Owner', prefix+'.Consumer',
            '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(data['classes']) == 6
    assert {item['symbol'] for item in data['classes']} == {'Owner', 'Consumer'}
    targets = set()
    for cls in data['classes']:
        path = cls['source_scope']['path']
        method = next(method for method in cls['methods'] if method['name'] == 'echo')
        handle = method['parameters'][0]['handle']
        from svx.source_scopes import instance_class_id
        assert handle['target_type_name'] == instance_class_id(path, 'Item')
        assert handle['sv_type'] == 'Item'
        targets.add(handle['target_type_name'])
    assert len(targets) == 3
    artifacts = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['systemverilog_compile_order'][0] == 'sv/native_handles.sv'
