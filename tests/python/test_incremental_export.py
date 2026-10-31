import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from svx.cli import main
from svx.source_selection import capture_selection, selection_context, validate_selection

pytest.importorskip('pyslang')


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'first').mkdir()
    (tmp_path / 'second').mkdir()
    (tmp_path / 'library').mkdir()
    (tmp_path / 'second/fields.svh').write_text('int count;\n', encoding='utf-8')
    source = tmp_path / 'classes.sv'
    source.write_text('''package p;class Driver;
`include "fields.svh"
function new(int seed);count=seed;endfunction
virtual function int status();return count;endfunction
endclass endpackage
module top; optional_cell u();endmodule''', encoding='utf-8')
    filelist = tmp_path / 'project.f'
    filelist.write_text('+incdir+first+second\n-y library +libext+.sv\nclasses.sv\n', encoding='utf-8')
    args = ['export', '--class', 'p::Driver', '-f', str(filelist),
            '--sv-build-directory', str(tmp_path), '--out', str(tmp_path / 'generated'), '--incremental']
    return args, tmp_path


def run(args):
    stream = io.StringIO()
    assert main(args, out=stream) == 0
    return stream.getvalue()


def test_noop_export_reuses_without_sv_parsing_and_check_is_readonly(project, monkeypatch):
    args, root = project
    assert 'full export' in run(args)
    cache = root / 'generated/.svx-export-cache.json'
    assert cache.is_file()
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in (root / 'generated').rglob('*') if path.is_file()}
    import svx.sv_scan as scan
    def forbidden(*args, **kwargs):
        pytest.fail('warm incremental export parsed SV source')
    monkeypatch.setattr(scan, '_parse_source_batch', forbidden)
    assert 'reused verified export' in run(args)
    assert 'reused verified export' in run(args + ['--check'])
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in (root / 'generated').rglob('*') if path.is_file()}


@pytest.mark.parametrize('change', ['source', 'include', 'earlier_include', 'new_library'])
def test_input_or_lookup_changes_force_full_discovery(project, change):
    args, root = project
    run(args)
    if change == 'source':
        path = root / 'classes.sv'
        path.write_text(path.read_text().replace('return count;', 'return count+1;'), encoding='utf-8')
    elif change == 'include':
        (root / 'second/fields.svh').write_text('int count;int extra;\n', encoding='utf-8')
    elif change == 'earlier_include':
        (root / 'first/fields.svh').write_text('int count;int earlier;\n', encoding='utf-8')
    else:
        (root / 'library/optional_cell.sv').write_text('module optional_cell;endmodule', encoding='utf-8')
    assert 'full export' in run(args)
    assert 'reused verified export' in run(args)


def test_changed_generated_output_is_not_accepted_as_cache_hit(project):
    args, root = project
    run(args)
    output = root / 'generated/mirrors.sv'
    original = output.read_text()
    output.write_text(original + '\n// user edit\n', encoding='utf-8')
    assert 'generated outputs changed' in run(args)
    assert output.read_text() == original


def test_changed_input_check_does_not_write_outputs_or_cache(project):
    args, root = project
    run(args)
    before = {path: path.read_bytes() for path in (root / 'generated').rglob('*') if path.is_file()}
    (root / 'first/fields.svh').write_text('int count;int earlier;\n', encoding='utf-8')
    with pytest.raises(SystemExit, match='stale'):
        run(args + ['--check'])
    assert before == {path: path.read_bytes() for path in (root / 'generated').rglob('*') if path.is_file()}


def test_force_refresh_rebuilds_and_check_remains_readonly(project, monkeypatch):
    args, root = project
    run(args)
    cache = root / 'generated/.svx-export-cache.json'
    before = cache.read_bytes(), cache.stat().st_mtime_ns
    assert 'forced refresh' in run(args + ['--refresh-cache', '--check'])
    assert (cache.read_bytes(), cache.stat().st_mtime_ns) == before
    assert 'reused verified export' in run(args)


def test_serialized_selection_replays_header_choice_without_parsing(project, monkeypatch):
    _, root = project
    source = root / 'classes.sv'
    options = {'include_dirs': [root / 'first', root / 'second']}
    proof = capture_selection([source], **options)
    assert proof is not None
    proof = json.loads(json.dumps(proof))
    context = selection_context([source], **options)
    import svx.sv_scan as scan
    monkeypatch.setattr(scan, '_parse_source_batch', lambda *a, **kw: pytest.fail('selection reparse'))
    assert validate_selection(proof, context)
    (root / 'first/fields.svh').write_text('int count;\n', encoding='utf-8')
    assert not validate_selection(proof, context)


def test_cache_reuse_crosses_fresh_python_processes(project):
    args, _ = project
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(root / 'python'), str(root.parent / 'svtypes/python')]))
    first = subprocess.run([sys.executable, '-B', '-m', 'svx', *args],
                           env=env, capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stdout + first.stderr
    code = '''import sys
import svx.sv_scan as scan
from svx.cli import entrypoint
def forbidden(*args,**kwargs):raise AssertionError('unexpected SV parse')
scan._parse_source_batch=forbidden
raise SystemExit(entrypoint(sys.argv[1:]))
'''
    second = subprocess.run([sys.executable, '-B', '-c', code, *args, '--check'],
                            env=env, capture_output=True, text=True, timeout=60)
    assert second.returncode == 0, second.stdout + second.stderr
    assert 'reused verified export' in second.stdout


def test_earlier_library_candidate_invalidates_cached_export(project):
    args, root = project
    filelist = root / 'project.f'
    filelist.write_text(filelist.read_text().replace('-y library', '-y first -y library'))
    (root / 'library/optional_cell.sv').write_text('module optional_cell;endmodule')
    run(args)
    (root / 'first/optional_cell.sv').write_text('module optional_cell;localparam int TAG=2;endmodule')
    assert 'include/library selection changed' in run(args)
    assert 'reused verified export' in run(args)


def test_macro_include_filename_uses_native_header_selection(project):
    args, root = project
    source = root / 'classes.sv'
    source.write_text('`define FILENAME "fields.svh"\n' +
                      source.read_text().replace('`include "fields.svh"', '`include `FILENAME'))
    run(args)
    assert 'reused verified export' in run(args)
    (root / 'first/fields.svh').write_text('int count;int replacement;')
    assert 'include/library selection changed' in run(args)


def test_mutation_between_hit_observations_falls_back_to_full_export(project, monkeypatch):
    args, root = project
    run(args)
    import svx.export_cache as cache
    original = cache.validate_selection
    calls = []
    def mutate(proof, context):
        calls.append(None)
        if len(calls) == 2:
            (root / 'second/fields.svh').write_text('int count;int changed;')
        return original(proof, context)
    monkeypatch.setattr(cache, 'validate_selection', mutate)
    assert 'inputs or outputs changed during verification' in run(args)
    assert 'changed' in (root / 'generated/mirrors.sv').read_text()


def test_changed_framework_fingerprint_does_not_reuse_cache(project, monkeypatch):
    args, _ = project
    run(args)
    import svx.export_cache as cache
    previous = cache._framework()
    monkeypatch.setattr(cache, '_framework', lambda: previous + '-updated')
    assert 'framework changed' in run(args)


def test_foreign_cache_path_is_never_overwritten(project):
    args, root = project
    run(args)
    cache = root / 'generated/.svx-export-cache.json'
    text = '{"owner": "user"}\n'
    cache.write_text(text)
    assert 'not owned by SVX' in run(args)
    assert cache.read_text() == text


@pytest.mark.parametrize('integrated', [False, True])
def test_cache_works_for_integrated_and_separate_output(project, integrated):
    args, _ = project
    if integrated:
        args += ['--integrated']
    run(args)
    assert 'reused verified export' in run(args + ['--check'])


def test_output_alias_retarget_does_not_reuse_relocated_provenance(project):
    args, root = project
    first = root / 'first_output'
    first.mkdir()
    alias = root / 'output_alias'
    try:
        alias.symlink_to(first, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('directory symbolic links are unavailable')
    args[args.index('--out') + 1] = str(alias)
    run(args)
    second = root / 'deeper/second_output'
    shutil.copytree(first, second)
    alias.unlink()
    alias.symlink_to(second, target_is_directory=True)
    assert 'request, build configuration or framework changed' in run(args)
    assert 'reused verified export' in run(args + ['--check'])


def test_unavailable_framework_fingerprint_falls_back_without_cache(project, monkeypatch):
    args, root = project
    import svx.export_cache as cache
    def unavailable():
        raise OSError('framework cannot be fingerprinted')
    monkeypatch.setattr(cache, '_framework', unavailable)
    assert 'framework fingerprint unavailable' in run(args)
    assert not (root / 'generated/.svx-export-cache.json').exists()


def test_optional_parser_error_keeps_the_normal_cli_diagnostic(tmp_path, monkeypatch):
    import builtins
    from svx.errors import SVXInheritanceError
    source = tmp_path / 'plain.sv'
    source.write_text('package p;class Driver;endclass endpackage')
    original = builtins.__import__
    def without_parser(name, *args, **kwargs):
        if name == 'pyslang':
            raise ModuleNotFoundError('pyslang')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_parser)
    with pytest.raises(SVXInheritanceError, match="optional 'pyslang'"):
        run(['export', '--class', 'p::Driver', '--sv-source', str(source),
             '--incremental', '--out', str(tmp_path / 'generated')])
