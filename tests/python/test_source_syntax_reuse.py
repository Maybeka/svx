from pathlib import Path
from types import SimpleNamespace

import pytest

from svx.source_selection import source_observations
from svx.sv_frontend import source_analysis
from svx.sv_library_search import library_search
from svx.sv_scan import _parse_sources, _pyslang, scan_sv_sources
from svx.sv_source_options import _source_dependencies, _source_parse_options

pytest.importorskip('pyslang')


def options(include_dirs=()):
    return _source_parse_options({}, (), include_dirs, discover_proxies=True)


def fields(source, parse_options):
    return tuple(item.name for item in scan_sv_sources([source], parse_options=parse_options)['p::C'].fields)


def test_dependency_capture_supplies_both_fresh_analysis_windows(tmp_path, monkeypatch):
    import svx.sv_scan as scanner

    source = tmp_path / 'source.sv'
    source.write_text('package p; class C; int first; endclass endpackage')
    parsed = []
    original = scanner._parse_source_batch

    def observed(*args, **kwargs):
        parsed.append(1)
        yield from original(*args, **kwargs)

    monkeypatch.setattr(scanner, '_parse_source_batch', observed)
    managers = []
    with source_observations() as observations:
        _source_dependencies([source])
        for _ in range(2):
            with source_analysis() as analysis:
                assert fields(source, options()) == ('first',)
                assert analysis.parse_batches == 0 and analysis.syntax_reuses >= 1
                managers.append(analysis.source_manager)
        assert observations.syntax_reuses == 2 and len(parsed) == 1
    assert managers[0] is managers[1]
    with source_observations(), source_analysis() as next_command:
        fields(source, options())
        assert next_command.parse_batches == 1
    assert len(parsed) == 2


@pytest.mark.parametrize('change', ['bytes', 'include_priority', 'parser_options'])
def test_cross_window_reuse_rejects_changed_inputs(tmp_path, change):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    source = tmp_path / 'source.sv'
    source.write_text('package p; class C; `include "field.svh"\n'
                      '`ifdef SELECT\nint selected;\n`endif\nendclass endpackage')
    header = second / 'field.svh'
    header.write_text('int first;\n')
    directories = [first, second]
    with source_observations():
        _source_dependencies([source], include_dirs=directories)
        parse_options = options(directories)
        if change == 'bytes':
            header.write_text('int changed;\n')
            expected = ('changed',)
        elif change == 'include_priority':
            (first / 'field.svh').write_text('int preferred;\n')
            expected = ('preferred',)
        else:
            parse_options.preprocessorOptions.predefines = ['SELECT']
            expected = ('first', 'selected')
        with source_analysis() as analysis:
            assert fields(source, parse_options) == expected
            assert analysis.parse_batches == 1


def test_cross_window_reuse_rejects_new_preferred_library(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    source = tmp_path / 'source.sv'
    source.write_text('package p; import base_pkg::*; class C extends Base; endclass endpackage')
    (second / 'base_pkg.sv').write_text('package base_pkg; class Base; int old; endclass endpackage')
    configuration = SimpleNamespace(library_dirs=(first, second), library_extensions=('.sv',), top_modules=())
    with library_search(configuration), source_observations():
        _source_dependencies([source])
        (first / 'base_pkg.sv').write_text('package base_pkg; class Base; int preferred; endclass endpackage')
        with source_analysis() as analysis:
            facts = scan_sv_sources([source], parse_options=options())
            assert facts['base_pkg::Base'].fields[0].name == 'preferred'
            assert analysis.parse_batches == 1


def test_explicit_source_manager_does_not_borrow_command_owned_storage(tmp_path):
    from pyslang import SourceManager

    source = tmp_path / 'source.sv'
    source.write_text('package p; class C; endclass endpackage')
    with source_observations():
        _source_dependencies([source])
        with source_analysis() as analysis:
            manager = SourceManager()
            tree, = _parse_sources(_pyslang(), [source], manager, parse_options=options())
            assert tree[1].sourceManager is manager
            assert analysis.parse_batches == 0 and analysis.syntax_reuses == 0


@pytest.mark.parametrize('spelling', ['relative', 'parent', 'symlink'])
def test_reused_syntax_preserves_native_file_macros_and_relative_headers(tmp_path, monkeypatch, spelling):
    from pyslang.ast import Compilation

    monkeypatch.chdir(tmp_path)
    real = tmp_path / 'real'
    real.mkdir()
    source = real / 'source.sv'
    source.write_text('package p; parameter string FILE=`__FILE__; '
                      'class C; `include "field.svh"\nendclass endpackage')
    (real / 'field.svh').write_text('int real_field;\n')
    (tmp_path / 'field.svh').write_text('int alias_field;\n')
    if spelling == 'relative':
        selected = Path('real/source.sv')
    elif spelling == 'parent':
        selected = real / '../real/source.sv'
    else:
        selected = tmp_path / 'alias.sv'
        try:
            selected.symlink_to(source)
        except (OSError, NotImplementedError):
            pytest.skip('file symlinks unavailable')

    def snapshot():
        trees = tuple(_parse_sources(_pyslang(), [selected], parse_options=options()))
        compilation = Compilation()
        for _, tree in trees:
            compilation.addSyntaxTree(tree)
        location = str(compilation.getPackage('p').lookupName('FILE').value)
        return location, fields(selected, options())

    expected = snapshot()
    with source_observations():
        _source_dependencies([source])
        with source_analysis():
            assert snapshot() == expected
