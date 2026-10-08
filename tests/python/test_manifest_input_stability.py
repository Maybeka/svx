import io
import json
import sys

import pytest

import svx.cli as cli
from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION
from svx.errors import SVXInheritanceError
from tests.integration.sv_field_mirror_schema import manifest_data


def args_for(tmp_path):
    declaration = tmp_path / 'declarations.json'
    declaration.write_text(json.dumps({'schema_uri': SV_DECLARATION_SCHEMA_URI,
                                      'schema_version': SV_DECLARATION_SCHEMA_VERSION,
                                      'classes': [manifest_data()['classes'][0]]}))
    return ['inheritance-manifest', '--sv-declarations', str(declaration),
            '--out', str(tmp_path / 'manifest.json')], declaration


@pytest.mark.parametrize('check', [False, True])
@pytest.mark.parametrize('changed_input', ['declarations', 'sv', 'include'])
def test_declaration_changed_during_discovery_preserves_manifest(tmp_path, monkeypatch, check, changed_input):
    args, source = args_for(tmp_path)
    sv_source = tmp_path / 'source.sv'
    include = tmp_path / 'settings.svh'
    include.write_text('`define SELECT 1\n')
    sv_source.write_text('`include "settings.svh"\npackage field_owner_pkg;\n'
                         'class Base; int count; function new(); endfunction\n'
                         'function int get_count(); return count; endfunction\n'
                         'function void set_count(input int value); count = value; endfunction\n'
                         'endclass endpackage\n')
    args += ['--sv-source', str(sv_source), '--sv-include-dir', str(tmp_path)]
    cli.main(args, out=io.StringIO())
    output = tmp_path / 'manifest.json'
    before = output.read_bytes(), output.stat().st_mtime_ns
    discover = cli.manifest_from_declarations
    def changed(**kwargs):
        result = discover(**kwargs)
        path = source if changed_input == 'declarations' else sv_source if changed_input == 'sv' else include
        path.write_text(path.read_text() + ('\n' if changed_input == 'declarations' else '// changed\n'))
        return result
    monkeypatch.setattr(cli, 'manifest_from_declarations', changed)
    with pytest.raises(SVXInheritanceError, match='manifest inputs changed during discovery'):
        cli.main(args + (['--check'] if check else []), out=io.StringIO())
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_self_editing_entry_module_is_rejected_before_manifest_write(tmp_path, monkeypatch):
    args, _ = args_for(tmp_path)
    name = 'svx_stability_self_editing_module'
    module = tmp_path / (name + '.py')
    module.write_text('from pathlib import Path\nPath(__file__).write_text("# changed during import\\n")\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        with pytest.raises(SVXInheritanceError, match='manifest inputs changed during discovery'):
            cli.main(args + ['--python-module', name], out=io.StringIO())
        assert not (tmp_path / 'manifest.json').exists()
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize('check', [False, True])
def test_deleted_declaration_during_discovery_keeps_output(tmp_path, monkeypatch, check):
    args, source = args_for(tmp_path)
    cli.main(args, out=io.StringIO())
    output = tmp_path / 'manifest.json'
    before = output.read_bytes(), output.stat().st_mtime_ns
    discover = cli.manifest_from_declarations
    def deleted(**kwargs):
        result = discover(**kwargs)
        source.unlink()
        return result
    monkeypatch.setattr(cli, 'manifest_from_declarations', deleted)
    with pytest.raises(SVXInheritanceError, match='manifest inputs could not be revalidated'):
        cli.main(args + (['--check'] if check else []), out=io.StringIO())
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


@pytest.mark.parametrize('check', [False, True])
@pytest.mark.parametrize('removed', [False, True])
def test_explicit_python_dependency_is_stable(tmp_path, monkeypatch, check, removed):
    args, _ = args_for(tmp_path)
    helper = tmp_path / 'codec_helper.py'
    helper.write_text('raise RuntimeError("fingerprinting must not execute this file")\n')
    args += ['--python-source', str(helper)]
    cli.main(args, out=io.StringIO())
    output = tmp_path / 'manifest.json'
    before = output.read_bytes(), output.stat().st_mtime_ns
    discover = cli.manifest_from_declarations

    def changed(**kwargs):
        result = discover(**kwargs)
        if removed:
            helper.unlink()
        else:
            helper.write_text('# helper changed\n')
        return result

    monkeypatch.setattr(cli, 'manifest_from_declarations', changed)
    message = 'could not be revalidated' if removed else 'changed during discovery.*python_sources'
    with pytest.raises(SVXInheritanceError, match=message):
        cli.main(args + (['--check'] if check else []), out=io.StringIO())
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_missing_explicit_python_input_fails_before_import(tmp_path, monkeypatch):
    args, _ = args_for(tmp_path)
    def unexpected_import(name):
        pytest.fail('missing dependency must be rejected before entry import')
    monkeypatch.setattr(cli.importlib, 'import_module', unexpected_import)
    with pytest.raises(SVXInheritanceError, match='Python source input is not a file'):
        cli.main(args + ['--python-module', 'unimported_entry',
                         '--python-source', str(tmp_path / 'missing.py')], out=io.StringIO())
    assert not (tmp_path / 'manifest.json').exists()


@pytest.mark.parametrize('alias', [False, True])
def test_manifest_output_cannot_overwrite_explicit_python_input(tmp_path, alias):
    args, _ = args_for(tmp_path)
    output = tmp_path / 'manifest.json'
    helper = tmp_path / 'helper.py' if alias else output
    helper.write_text('# protected user source\n')
    if alias:
        output.hardlink_to(helper)
    before = helper.read_bytes(), helper.stat().st_mtime_ns
    with pytest.raises(SVXInheritanceError, match='input'):
        cli.main(args + ['--python-source', str(helper)], out=io.StringIO())
    assert (helper.read_bytes(), helper.stat().st_mtime_ns) == before
    assert output.read_bytes() == before[0]
