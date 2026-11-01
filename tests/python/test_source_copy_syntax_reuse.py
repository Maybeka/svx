import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from svx.cli import main
from svx.source_selection import borrow_source_copy_syntax, source_observations
from svx.sv_library_search import library_search
from svx.sv_source_options import _source_dependencies, _source_parse_options

pytest.importorskip('pyslang')


@pytest.mark.parametrize('shared', [False, True])
def test_actual_unit_export_borrows_original_roots_and_preserves_outputs(tmp_path, monkeypatch, shared):
    import svx.source_selection as selection

    first, second = tmp_path / 'first.sv', tmp_path / 'second.sv'
    header = tmp_path / 'field.svh'
    header.write_text('int included;\n', encoding='utf-8')
    first.write_text('class First;\n`include "field.svh"\n'
                     'function new();included=11;endfunction endclass\n', encoding='utf-8')
    second.write_text('class Second;int value;function new();value=22;endfunction endclass\n', encoding='utf-8')
    args = ['export', '--class', 'First', 'Second', '--sv-source', str(first),
            '--sv-source', str(second)] + (['--sv-compilation-unit'] if shared else [])
    original = selection.borrow_source_copy_syntax
    baseline, output = tmp_path / 'baseline', tmp_path / 'generated'
    monkeypatch.setattr(selection, 'borrow_source_copy_syntax', lambda *a, **kw: None)
    main([*args, '--out', str(baseline)], out=io.StringIO())
    borrowed = []
    def observe(*a, **kw):
        result = original(*a, **kw)
        assert result is not None
        snapshot, buffers = result
        assert len(snapshot.root_trees) == (1 if shared else 2)
        assert set(buffers) == {str(first), str(second)}
        borrowed.append(snapshot)
        return result
    monkeypatch.setattr(selection, 'borrow_source_copy_syntax', observe)
    main([*args, '--out', str(output)], out=io.StringIO())
    main([*args, '--out', str(output), '--check'], out=io.StringIO())
    assert len(borrowed) == 2
    assert {path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()} == {
        path.relative_to(baseline): path.read_bytes() for path in baseline.rglob('*') if path.is_file()}


@pytest.mark.parametrize('change', ['text', 'header', 'options', 'newline'])
def test_source_copy_never_borrows_stale_or_transformed_text(tmp_path, change):
    source = tmp_path / 'source.sv'
    header = tmp_path / 'field.svh'
    header.write_text('int included;\n', encoding='utf-8')
    source.write_text('class First;\n`include "field.svh"\nendclass\n', encoding='utf-8')
    sources = {str(source): source.read_text(encoding='utf-8')}
    with source_observations():
        _source_dependencies([source])
        options = _source_parse_options({}, (), (), discover_proxies=True)
        valid = borrow_source_copy_syntax(sources, options, False)
        assert valid is not None
        manager = valid[0].source_manager
        before = tuple(manager.getAllBuffers())
        if change == 'text':
            sources[str(source)] = sources[str(source)].replace('First', 'Changed')
        elif change == 'header':
            header.write_text('int changed;\n', encoding='utf-8')
        elif change == 'options':
            options.preprocessorOptions.predefines = ['NEW_MACRO']
        else:
            sources[str(source)] = sources[str(source)].replace('\n', '\r\n')
        assert borrow_source_copy_syntax(sources, options, False) is None
        assert tuple(manager.getAllBuffers()) == before


def test_source_copy_keeps_explicit_roots_separate_from_demanded_libraries(tmp_path, monkeypatch):
    import svx.source_selection as selection
    library = tmp_path / 'library'
    library.mkdir()
    (library / 'base_pkg.sv').write_text('package base_pkg;class Base;int value;endclass endpackage', encoding='utf-8')
    source = tmp_path / 'source.sv'
    source.write_text('import base_pkg::*;class Child extends Base;endclass', encoding='utf-8')
    config = SimpleNamespace(library_dirs=(library,), library_extensions=('.sv',), top_modules=())
    with library_search(config), source_observations():
        _source_dependencies([source])
        options = _source_parse_options({}, (), (), discover_proxies=True)
        result = borrow_source_copy_syntax({str(source): source.read_text(encoding='utf-8')}, options, False)
        assert result is not None
        snapshot, _ = result
        assert len(snapshot.root_trees) == 1
        assert any(tree.isLibraryUnit for _, tree in snapshot.trees)
        assert not snapshot.root_trees[0][1].isLibraryUnit
    filelist = tmp_path / 'project.f'
    filelist.write_text('-y library +libext+.sv\nsource.sv\n', encoding='utf-8')
    args = ['export', '--class', 'Child', '-f', str(filelist), '--sv-build-directory', str(tmp_path)]
    baseline, output = tmp_path / 'baseline', tmp_path / 'generated'
    original = selection.borrow_source_copy_syntax
    monkeypatch.setattr(selection, 'borrow_source_copy_syntax', lambda *a, **kw: None)
    main([*args, '--out', str(baseline)], out=io.StringIO())
    observations = []
    def observe(*a, **kw):
        result = original(*a, **kw)
        observations.append(result is not None)
        return result
    monkeypatch.setattr(selection, 'borrow_source_copy_syntax', observe)
    main([*args, '--out', str(output)], out=io.StringIO())
    assert observations == [True]
    assert {path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()} == {
        path.relative_to(baseline): path.read_bytes() for path in baseline.rglob('*') if path.is_file()}


@pytest.mark.parametrize('shared', [False, True])
def test_package_source_copy_reuses_roots_without_changing_generated_products(tmp_path, monkeypatch, shared):
    import svx.source_selection as selection
    sources = []
    for index in range(2):
        header = tmp_path / f'field{index}.svh'
        header.write_text(f'int value{index};\n', encoding='utf-8')
        source = tmp_path / f'package{index}.sv'
        source.write_text(f'package p{index};parameter string FILE=`__FILE__;class C{index};\n'
                          f'`include "field{index}.svh"\nendclass endpackage\n', encoding='utf-8')
        sources.append(source)
    args = ['export', '--package', 'p0', 'p1', '--integrated']
    for source in sources:
        args.extend(['--sv-source', str(source)])
    if shared:
        args.append('--sv-compilation-unit')
    original = selection.borrow_source_copy_syntax
    baseline, output = tmp_path / 'baseline', tmp_path / 'generated'
    monkeypatch.setattr(selection, 'borrow_source_copy_syntax', lambda *a, **kw: None)
    main([*args, '--out', str(baseline)], out=io.StringIO())
    observations = []
    def observe(*a, **kw):
        result = original(*a, **kw)
        observations.append(result is not None)
        return result
    monkeypatch.setattr(selection, 'borrow_source_copy_syntax', observe)
    main([*args, '--out', str(output)], out=io.StringIO())
    assert any(observations)
    assert {path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()} == {
        path.relative_to(baseline): path.read_bytes() for path in baseline.rglob('*') if path.is_file()}
