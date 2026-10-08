import io
import pytest

import svx.cli as cli
from svx.errors import SVXInheritanceError
from tests.python.test_python_source_inputs import generation_args


@pytest.mark.parametrize('changed_input', ['python', 'manifest', 'sv', 'include'])
@pytest.mark.parametrize('check', [False, True])
def test_input_edit_during_emission_is_rejected_without_output_changes(tmp_path, monkeypatch, changed_input, check):
    source = tmp_path / 'source.py'
    source.write_text('# selected Python input\n')
    args = generation_args(tmp_path, source)
    sv_source = tmp_path / 'source.sv'
    include = tmp_path / 'settings.svh'
    include.write_text('`define SELECT 1\n')
    sv_source.write_text('`include "settings.svh"\nmodule top; endmodule\n')
    args += ['--sv-source', str(sv_source), '--sv-include-dir', str(tmp_path)]
    cli.main(args, out=io.StringIO())
    outputs = {path: (path.read_bytes(), path.stat().st_mtime_ns)
               for path in tmp_path.rglob('*') if path.is_file()
               and path not in (source, sv_source, include, tmp_path / 'manifest.json')}
    emit = cli.emit_python_mirrors
    def edited_emission(manifest):
        result = emit(manifest)
        if changed_input == 'manifest':
            path = tmp_path / 'manifest.json'
            path.write_text(path.read_text() + '\n')
        else:
            path = source if changed_input == 'python' else include if changed_input == 'include' else sv_source
            path.write_text(path.read_text() + ('# edited\n' if changed_input == 'python' else '// edited\n'))
        return result
    monkeypatch.setattr(cli, 'emit_python_mirrors', edited_emission)
    with pytest.raises(SVXInheritanceError, match='inputs changed during generation'):
        cli.main(args + (['--check'] if check else []), out=io.StringIO())
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in outputs} == outputs


def test_initial_generation_with_input_edit_does_not_create_outputs(tmp_path, monkeypatch):
    source = tmp_path / 'source.py'
    source.write_text('# original\n')
    args = generation_args(tmp_path, source)
    load = cli.load_manifest
    def edited_load(path):
        result = load(path)
        source.write_text('# edited during manifest materialization\n')
        return result
    monkeypatch.setattr(cli, 'load_manifest', edited_load)
    with pytest.raises(SVXInheritanceError, match='inputs changed during generation'):
        cli.main(args, out=io.StringIO())
    assert not (tmp_path / 'python').exists()
    assert not (tmp_path / 'mirrors.sv').exists()
    assert not (tmp_path / 'artifacts.json').exists()


@pytest.mark.parametrize('check', [False, True])
def test_input_removed_during_generation_is_rejected_before_writes(tmp_path, monkeypatch, check):
    source = tmp_path / 'source.py'
    source.write_text('# original\n')
    args = generation_args(tmp_path, source)
    cli.main(args, out=io.StringIO())
    artifacts_before = (tmp_path / 'artifacts.json').read_bytes()
    emit = cli.emit_python_mirrors
    def deleted_emission(manifest):
        result = emit(manifest)
        source.unlink()
        return result
    monkeypatch.setattr(cli, 'emit_python_mirrors', deleted_emission)
    with pytest.raises(SVXInheritanceError, match='inputs could not be revalidated'):
        cli.main(args + (['--check'] if check else []), out=io.StringIO())
    assert (tmp_path / 'artifacts.json').read_bytes() == artifacts_before
