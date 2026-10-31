from contextlib import contextmanager
from types import ModuleType, SimpleNamespace

import pytest

import svx.sv_frontend as frontend
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.sv_scan import _parse_sources, _pyslang, scan_sv_sources
from svx.sv_source_options import _source_parse_options


pytest.importorskip('pyslang')


@pytest.mark.parametrize('shared', [False, True])
def test_raw_syntax_shared_across_semantic_consumers(tmp_path, shared):
    source = tmp_path / 'driver.sv'
    source.write_text('package drivers; class Base; int count; '
                      'virtual function int status(); return count; endfunction '
                      'endclass endpackage', encoding='utf-8')
    module = ModuleType('analysis_driver')
    exec('import svx\n@svx.sv_mirror("sv://drivers/Base")\n'
         'class Mirror(svx.SVMirror): pass\n@svx.inheritance_class()\n'
         'class Driver(Mirror): pass\n', module.__dict__)
    kwargs = dict(python_modules=[module], sv_source_files=[source], sv_compilation_unit=shared)
    expected = manifest_dict(manifest_from_declarations(**kwargs))
    with frontend.source_analysis() as analysis:
        actual = manifest_dict(manifest_from_declarations(**kwargs))
    assert actual == expected
    assert analysis.parse_batches == 1
    assert analysis.syntax_reuses >= 5
    assert analysis.parse_seconds > 0


def test_cli_generation_enrichment_shares_one_parse_but_not_discovery_state(tmp_path, monkeypatch):
    from io import StringIO
    from svx.cli import main
    from tests.python.test_semantic_handle_discovery import source_file

    source = source_file(tmp_path)
    sessions = []
    original = frontend.source_analysis
    @contextmanager
    def observed():
        with original() as state:
            sessions.append(state)
            yield state
    monkeypatch.setattr(frontend, 'source_analysis', observed)
    args = ['export', '--class', 'p::A', '--sv-source', str(source),
            '--out', str(tmp_path / 'generated')]
    assert main(args, out=StringIO()) == 0
    assert len(sessions) == 2
    discovery, generation = sessions
    assert generation is not discovery
    assert generation.source_manager is not discovery.source_manager
    assert generation.parse_batches == 1 and generation.syntax_reuses >= 3
    assert main(args + ['--check'], out=StringIO()) == 0
    assert len(sessions) == 4 and sessions[-1].parse_batches == 1
    assert sessions[-1].source_manager is not generation.source_manager
    assert frontend._analysis.get() is None


def test_sessions_do_not_retain_previous_source_bytes(tmp_path):
    source = tmp_path / 'driver.sv'
    source.write_text('package drivers; class First; endclass endpackage', encoding='utf-8')
    with frontend.source_analysis() as first:
        assert 'drivers::First' in scan_sv_sources([source])
        with frontend.source_analysis() as nested:
            scan_sv_sources([source])
            assert nested.parse_batches == 1
        scan_sv_sources([source])
        assert first.parse_batches == 1 and first.syntax_reuses == 1
    source.write_text('package drivers; class Second; endclass endpackage', encoding='utf-8')
    with frontend.source_analysis() as second:
        assert set(scan_sv_sources([source])) == {'drivers::Second'}
        assert second.parse_batches == 1
    assert frontend._analysis.get() is None


def test_parse_options_and_compilation_units_are_not_conflated(tmp_path):
    source = tmp_path / 'conditional.sv'
    source.write_text('package drivers; `ifdef SELECT\nclass Selected; endclass\n'
                      '`else\nclass Default; endclass\n`endif\nendpackage', encoding='utf-8')
    selected = _source_parse_options({'SELECT': None}, (), ())
    default = _source_parse_options({}, (), ())
    with frontend.source_analysis() as analysis:
        assert set(scan_sv_sources([source], parse_options=selected)) == {'drivers::Selected'}
        assert set(scan_sv_sources([source], parse_options=default)) == {'drivers::Default'}
        scan_sv_sources([source], parse_options=default, compilation_unit=True)
        assert analysis.parse_batches == 3


def test_explicit_foreign_manager_is_not_replaced(tmp_path):
    from pyslang import SourceManager

    source = tmp_path / 'driver.sv'
    source.write_text('package drivers; endpackage', encoding='utf-8')
    manager = SourceManager()
    with frontend.source_analysis() as analysis:
        trees = tuple(_parse_sources(_pyslang(), [source], manager))
        assert trees[0][1].sourceManager is manager
        assert analysis.parse_batches == 0


def test_proxy_context_is_applied_after_raw_syntax_reuse(tmp_path, monkeypatch):
    import svx.sv_scan as scan

    source = tmp_path / 'driver.sv'
    source.write_text('package drivers; endpackage', encoding='utf-8')
    contexts = []
    def transform(tree, context):
        contexts.append(context)
        return tree
    monkeypatch.setattr(scan, '_with_python_proxy_members', transform)
    with frontend.source_analysis() as analysis:
        tuple(_parse_sources(_pyslang(), [source], proxy_context=('first',)))
        tuple(_parse_sources(_pyslang(), [source], proxy_context=('second',)))
        assert analysis.parse_batches == 1 and analysis.syntax_reuses == 1
    assert contexts == [('first',), ('second',)]


def test_failed_analysis_scope_does_not_leak():
    with pytest.raises(RuntimeError):
        with frontend.source_analysis():
            raise RuntimeError('failed discovery')
    assert frontend._analysis.get() is None


def test_semantic_consumers_share_only_identical_command_trees(tmp_path):
    source = tmp_path / 'driver.sv'
    source.write_text('package drivers; class Base; endclass '
                      'typedef Base Alias; endpackage', encoding='utf-8')
    with frontend.source_analysis() as analysis:
        scan_sv_sources([source])
        trees = tuple(tree for _, tree in _parse_sources(_pyslang(), [source]))
        first = frontend.compile_source_trees(trees)
        assert frontend.compile_source_trees(trees) is first
        assert analysis.semantic_builds == 1 and analysis.semantic_reuses == 2
        assert analysis.semantic_seconds > 0
        with frontend.source_elaboration('packages'):
            other = frontend.compile_source_trees(trees)
            assert other is not first
            assert other.getRoot().topInstances[0].name == 'svx_export_analysis_root'
        assert frontend.compile_source_trees(trees) is first
        assert analysis.semantic_builds == 2
        probe = _pyslang().SyntaxTree.fromText('package probe; endpackage', analysis.source_manager)
        checked = frontend.compile_source_trees((*trees, probe))
        assert checked is not first and checked.getPackage('probe') is not None
        assert first.getPackage('probe') is None
    with frontend.source_analysis() as next_analysis:
        assert frontend.compile_source_trees(trees) is not first
        assert next_analysis.semantic_builds == 0


def test_semantic_reuse_preserves_library_top_selection():
    from svx.sv_library_search import library_search

    with frontend.source_analysis() as analysis:
        tree = _pyslang().SyntaxTree.fromText(
            'module First; endmodule module Second; endmodule', analysis.source_manager)
        def configuration(name):
            return SimpleNamespace(library_dirs=(), library_extensions=(), top_modules=(name,))
        with library_search(configuration('First')):
            first = frontend.compile_source_trees((tree,))
            assert [item.name for item in first.getRoot().topInstances] == ['First']
            with library_search(configuration('Second')):
                second = frontend.compile_source_trees((tree,))
                assert second is not first
                assert [item.name for item in second.getRoot().topInstances] == ['Second']
            assert frontend.compile_source_trees((tree,)) is first
        assert analysis.semantic_builds == 2 and analysis.semantic_reuses == 1


def test_cli_shares_discovery_but_not_source_revalidation(tmp_path, monkeypatch):
    import io
    import svx.cli as cli
    from tests.python.test_manifest_input_stability import args_for

    args, _ = args_for(tmp_path)
    source = tmp_path / 'source.sv'
    source.write_text('package field_owner_pkg; class Base; int count; '
                      'function new(); endfunction '
                      'function int get_count(); return count; endfunction '
                      'function void set_count(input int value); count=value; endfunction '
                      'endclass endpackage', encoding='utf-8')
    original = frontend.source_analysis
    scopes = []
    @contextmanager
    def observed():
        with original() as state:
            scopes.append(state)
            yield state
    monkeypatch.setattr(frontend, 'source_analysis', observed)
    assert cli.main(args + ['--sv-source', str(source)], out=io.StringIO()) == 0
    assert len(scopes) == 1 and scopes[0].parse_batches == 1
    assert scopes[0].syntax_reuses >= 4
    assert frontend._analysis.get() is None
