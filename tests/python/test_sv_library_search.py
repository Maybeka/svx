import io
import json
from pathlib import Path

import pytest

from svx.cli import main
from svx.compile_config import import_compile_configuration
from svx.errors import SVXInheritanceError
from svx.sv_library_search import library_search
from svx.sv_scan import _parse_sources, _pyslang
from svx.sv_source_options import _source_dependencies, _source_parse_options


def configuration(tmp_path, text):
    filelist = tmp_path / 'files.f'
    filelist.write_text(text)
    return import_compile_configuration(dict(directory=str(tmp_path), filelists=[str(filelist)]))


def parse(config):
    with library_search(config):
        trees = list(_parse_sources(_pyslang(), config.sources,
                    parse_options=_source_parse_options(config.defines, config.undefines, config.include_dirs),
                    compilation_unit=config.shared))
        return [(str(tree.root), tree.isLibraryUnit) for _, tree in trees]


def fixture(tmp_path):
    for name in ('first', 'second'):
        (tmp_path / name).mkdir()
    (tmp_path / 'top.sv').write_text('module top; cell_unit u(); endmodule\n')
    (tmp_path / 'first/cell_unit.alt').write_text('module cell_unit; leaf u(); endmodule\n')
    (tmp_path / 'first/cell_unit.sv').write_text('module cell_unit; endmodule\n')
    (tmp_path / 'second/cell_unit.alt').write_text('module cell_unit; endmodule\n')
    (tmp_path / 'first/leaf.alt').write_text('module leaf; endmodule\n')
    (tmp_path / 'first/unused.alt').write_text('this is deliberately invalid SV !')


def dependencies(config):
    with library_search(config):
        return _source_dependencies(config.sources, predefines=config.defines,
                     undefines=config.undefines, include_dirs=config.include_dirs,
                     compilation_unit=config.shared)


def test_demand_search_directory_then_extension_order_and_transitive_loading(tmp_path):
    fixture(tmp_path)
    config = configuration(tmp_path, '-y first -y second +libext+.alt+.sv\ntop.sv')
    assert config.sources == [tmp_path / 'top.sv']
    selected = dependencies(config)
    assert selected == {tmp_path / name for name in ('top.sv', 'first/cell_unit.alt', 'first/leaf.alt')}
    trees = parse(config)
    assert len(trees) == 3
    assert sum(is_library for _, is_library in trees) == 2


@pytest.mark.parametrize('options,expected', [
    ('-y second -y first +libext+.alt+.sv', 'second/cell_unit.alt'),
    ('-y first -y second +libext+.sv+.alt', 'first/cell_unit.sv'),
])
def test_reordering_selects_original_first_candidate(tmp_path, options, expected):
    fixture(tmp_path)
    config = configuration(tmp_path, options + '\ntop.sv')
    assert dependencies(config) == {tmp_path / 'top.sv', tmp_path / expected}


def test_no_extra_default_suffixes_are_added(tmp_path):
    fixture(tmp_path)
    config = configuration(tmp_path, '-y first +libext+.other\ntop.sv')
    assert dependencies(config) == {tmp_path / 'top.sv'}


def test_explicit_definition_wins_without_library_file_loading(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'top.sv').write_text('module top; cell_unit u(); endmodule module cell_unit; endmodule')
    config = configuration(tmp_path, '-y first +libext+.alt\ntop.sv')
    assert dependencies(config) == {tmp_path / 'top.sv'}


def test_library_search_context_does_not_leak(tmp_path):
    fixture(tmp_path)
    config = configuration(tmp_path, '-y first +libext+.alt\ntop.sv')
    assert len(dependencies(config)) == 3
    assert _source_dependencies(config.sources) == {tmp_path / 'top.sv'}


def test_selected_invalid_library_is_not_skipped(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'first/cell_unit.alt').write_text('not valid SV !')
    config = configuration(tmp_path, '-y first -y second +libext+.alt\ntop.sv')
    with pytest.raises(SVXInheritanceError, match='cannot parse'):
        parse(config)


def test_shared_macros_are_available_to_selected_library(tmp_path):
    (tmp_path / 'lib').mkdir()
    (tmp_path / 'top.sv').write_text('`define WIDTH 8\nmodule top; unit_cell u(); endmodule')
    (tmp_path / 'lib/unit_cell.sv').write_text('module unit_cell; bit [`WIDTH-1:0] value; endmodule')
    config = configuration(tmp_path, '--single-unit -y lib +libext+.sv\ntop.sv')
    assert len(parse(config)) == 2


@pytest.mark.parametrize('shared', [False, True])
def test_library_chain_visits_only_new_trees_and_does_not_reload_previous_libraries(tmp_path, monkeypatch, shared):
    from pyslang import driver
    import svx.sv_library_search as search

    count = 12
    (tmp_path / 'top.sv').write_text('module top; l0 u(); endmodule')
    for index in range(count):
        (tmp_path / f'l{index}.sv').write_text(f'module l{index}; ' +
            (f'l{index+1} u(); ' if index + 1 < count else '') + 'endmodule')
    config = configuration(tmp_path, ('--single-unit ' if shared else '') + '-y . +libext+.sv\ntop.sv')
    original_symbols, original_loader = search._symbols, driver.SourceLoader
    sizes, roots, libraries = [], [], []

    def symbols(trees):
        sizes.append(len(trees))
        return original_symbols(trees)

    class Loader:
        def __init__(self, manager):
            self.native = original_loader(manager)

        def addFiles(self, filename):
            roots.append(filename)
            return self.native.addFiles(filename)

        def addLibraryFiles(self, name, filename):
            libraries.append(filename)
            return self.native.addLibraryFiles(name, filename)

        def __getattr__(self, name):
            return getattr(self.native, name)

    monkeypatch.setattr(search, '_symbols', symbols)
    monkeypatch.setattr(driver, 'SourceLoader', Loader)
    trees = parse(config)
    assert len(trees) == count + 1
    assert sizes == [1] * (count + 1)
    assert libraries == [str(tmp_path / f'l{i}.sv') for i in range(count)]
    assert len(roots) == (count if shared else 0)


def test_new_library_definitions_suppress_later_pending_lookups(tmp_path):
    (tmp_path / 'top.sv').write_text('module top; alpha a(); beta b(); endmodule')
    (tmp_path / 'alpha.sv').write_text('module alpha; endmodule module beta; endmodule')
    (tmp_path / 'beta.sv').write_text('deliberately invalid unselected candidate')
    config = configuration(tmp_path, '-y . +libext+.sv\ntop.sv')
    assert len(parse(config)) == 2


def test_shared_libraries_inherit_root_macros_but_not_previous_library_macros(tmp_path):
    (tmp_path / 'top.sv').write_text('`define WIDTH 13\nmodule top; alpha a(); endmodule')
    (tmp_path / 'alpha.sv').write_text('`define PRIVATE_MACRO\nmodule alpha; beta b(); endmodule')
    (tmp_path / 'beta.sv').write_text('module beta;\n`ifdef PRIVATE_MACRO\ninvalid syntax !\n`endif\n'
                                    'bit [`WIDTH-1:0] value; endmodule')
    config = configuration(tmp_path, '--single-unit -y . +libext+.sv\ntop.sv')
    trees = parse(config)
    assert len(trees) == 3
    assert 'bit [13-1:0]' in trees[-1][0]


def test_class_export_check_detects_new_earlier_library_candidate(tmp_path):
    from tests.integration.sv_field_mirror_schema import manifest_data
    fixture(tmp_path)
    (tmp_path / 'first/cell_unit.alt').unlink()
    source = tmp_path / 'classes.sv'
    source.write_text(Path('tests/integration/sv_field_owner.sv').read_text())
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(manifest_data()))
    filelist = tmp_path / 'files.f'
    filelist.write_text('-y first -y second +libext+.alt\ntop.sv classes.sv')
    args = ['inheritance-gen', '--manifest', str(manifest), '--sv-filelist', str(filelist),
            '--sv-build-directory', str(tmp_path), '--python-out', str(tmp_path / 'python'),
            '--sv-out', str(tmp_path / 'bridge.sv'), '--artifact-manifest', str(tmp_path / 'artifacts.json')]
    main(args, out=io.StringIO())
    main([*args, '--check'], out=io.StringIO())
    (tmp_path / 'first/unused.alt').write_text('changed unrelated invalid source !')
    main([*args, '--check'], out=io.StringIO())
    outputs = [tmp_path / 'bridge.sv', tmp_path / 'artifacts.json', *(tmp_path / 'python').rglob('*.py')]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in outputs}
    (tmp_path / 'first/cell_unit.alt').write_text('module cell_unit; endmodule')
    with pytest.raises(SystemExit, match='stale'):
        main([*args, '--check'], out=io.StringIO())
    assert all((p.read_bytes(), p.stat().st_mtime_ns) == data for p, data in before.items())
