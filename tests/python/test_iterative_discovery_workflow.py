"""Exercise both public generation stages in fresh command processes."""

import os
import py_compile
import importlib
from pathlib import Path
import subprocess
import sys
import json

from svx.cli import _fresh_declaration_entries


def run_cli(root, *args, preload=()):
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(root), str(repo / 'python'),
                                       str(repo.parent / 'svtypes' / 'python'),
                                       env.get('PYTHONPATH', '')])
    command = [sys.executable, '-m', 'svx', *args]
    if preload:
        command = [sys.executable, '-c',
                   'import importlib, sys; '
                   f'[importlib.import_module(name) for name in {preload!r}]; '
                   'from svx.cli import main; sys.exit(main(sys.argv[1:]))', *args]
    result = subprocess.run(command, cwd=root,
                            env=env, capture_output=True, text=True, timeout=30)
    return result


def test_framework_preloads_do_not_change_user_import_provenance(tmp_path):
    from tests.integration.sv_field_mirror_schema import manifest_data

    preloads = ('svtypes.constraint.backend.sv', 'svtypes.coverage.sv')
    (tmp_path / 'user_helper.py').write_text('VALUE = 8\n')
    (tmp_path / 'user_factory.py').write_text(
        'import user_helper\nimport svtypes.constraint.backend.sv\n'
        'import svtypes.coverage.sv\nfrom svtypes import Int\n'
        'def make(): return Int(user_helper.VALUE)\n')
    data = manifest_data()
    binding = data['classes'][0]['fields'][0]['type']
    binding.pop('svtypes')
    binding['python'] = {'module': 'user_factory', 'symbol': 'make'}
    (tmp_path / 'manifest.json').write_text(json.dumps(data))
    outputs = tmp_path / 'generated'
    args = ('inheritance-gen', '--manifest', str(tmp_path / 'manifest.json'),
            '--python-out', str(outputs / 'python'), '--sv-out', str(outputs / 'mirrors.sv'),
            '--artifact-manifest', str(outputs / 'artifacts.json'))
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    baseline = snapshot(outputs)
    records = json.loads((outputs / 'artifacts.json').read_text())['generation_inputs']['python_imports']
    assert {item['path'] for item in records} == {'../user_factory.py', '../user_helper.py'}
    for preload in (preloads, ()):
        for flags in (('--check',), ()):
            result = run_cli(tmp_path, *args, *flags, preload=preload)
            assert result.returncode == 0, result.stderr
            assert snapshot(outputs) == baseline
    (tmp_path / 'user_helper.py').write_text('VALUE = 9\n')
    result = run_cli(tmp_path, *args, '--check', preload=preloads)
    assert result.returncode != 0
    assert 'user_helper.py' in result.stderr
    assert snapshot(outputs) == baseline


def source_text(result=1, parameter=False):
    formal = ', value: svtypes.Int' if parameter else ''
    return ('import svtypes\nimport svx\n'
            '@svx.inheritance_class(canonical_id="py://iteration/Driver")\n'
            'class Driver:\n'
            '    @svx.inheritance_method\n'
            f'    def calculate(self{formal}) -> svx.Function[svtypes.Int]:\n'
            f'        return {result}\n')


def test_standard_library_preload_does_not_change_discovery_evidence(tmp_path):
    source = tmp_path / 'stdlib_owner.py'
    source.write_text(source_text().replace('import svtypes\n', 'import colorsys\nimport svtypes\n'))
    manifest = tmp_path / 'generated' / 'manifest.json'
    arguments = ('inheritance-manifest', '--python-module', 'stdlib_owner', '--out', str(manifest))
    result = run_cli(tmp_path, *arguments)
    assert result.returncode == 0, result.stderr
    baseline = snapshot(manifest.parent)
    record = json.loads(manifest.with_name(manifest.name + '.svx-discovery.json').read_text())
    assert {item['path'] for item in record['sources']} == {'../stdlib_owner.py'}
    for flags in (('--check',), ()):
        result = run_cli(tmp_path, *arguments, *flags, preload=('colorsys',))
        assert result.returncode == 0, result.stderr
        assert snapshot(manifest.parent) == baseline


def test_standard_library_preload_does_not_change_generation_evidence(tmp_path):
    from tests.integration.sv_field_mirror_schema import manifest_data

    (tmp_path / 'stdlib_factory.py').write_text(
        'import colorsys\nfrom svtypes import Int\ndef make(): return Int()\n')
    data = manifest_data()
    binding = data['classes'][0]['fields'][0]['type']
    binding.pop('svtypes')
    binding['python'] = {'module': 'stdlib_factory', 'symbol': 'make'}
    (tmp_path / 'manifest.json').write_text(json.dumps(data))
    output = tmp_path / 'generated'
    args = ('inheritance-gen', '--manifest', str(tmp_path / 'manifest.json'),
            '--python-out', str(output / 'python'), '--sv-out', str(output / 'mirrors.sv'),
            '--artifact-manifest', str(output / 'artifacts.json'))
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    baseline = snapshot(output)
    records = json.loads((output / 'artifacts.json').read_text())['generation_inputs']['python_imports']
    assert {entry['path'] for entry in records} == {'../stdlib_factory.py'}
    for flags in (('--check',), ()):
        result = run_cli(tmp_path, *args, *flags, preload=('colorsys',))
        assert result.returncode == 0, result.stderr
        assert snapshot(output) == baseline


def test_stdlib_filter_does_not_exclude_installed_user_packages(tmp_path, monkeypatch):
    from svx.cli import _is_framework_source
    import svx.cli

    stdlib = tmp_path / 'stdlib'
    monkeypatch.setattr(svx.cli, '_STDLIB_SOURCE_ROOTS', (stdlib,))
    assert _is_framework_source(stdlib / 'colorsys.py')
    assert _is_framework_source(stdlib / 'email' / 'parser.py')
    assert not _is_framework_source(stdlib / 'site-packages' / 'colorsys.py')
    assert not _is_framework_source(stdlib / 'dist-packages' / 'user_codec.py')
    assert not _is_framework_source(stdlib / 'user_codec.py')
    assert not _is_framework_source(tmp_path / 'colorsys.py')


def test_framework_filter_keeps_component_boundaries_and_current_symlink_roots(tmp_path, monkeypatch):
    from types import ModuleType
    import svx.cli

    package = ModuleType('pyslang')
    first, second = tmp_path / 'framework', tmp_path / 'replacement'
    first.mkdir()
    second.mkdir()
    alias = tmp_path / 'framework-link'
    alias.symlink_to(first, target_is_directory=True)
    package.__path__ = [str(alias)]
    monkeypatch.setitem(sys.modules, 'pyslang', package)
    monkeypatch.setattr(svx.cli, '_STDLIB_SOURCE_ROOTS', ())
    def reject_parent_construction(*args):
        raise AssertionError('recursive pathlib containment')

    monkeypatch.setattr(Path, 'is_relative_to', reject_parent_construction)
    assert svx.cli._is_framework_source(first / 'codec.py')
    assert not svx.cli._is_framework_source(tmp_path / 'framework-other' / 'codec.py')
    alias.unlink()
    alias.symlink_to(second, target_is_directory=True)
    assert not svx.cli._is_framework_source(first / 'codec.py')
    assert svx.cli._is_framework_source(second / 'codec.py')


def test_framework_filter_canonical_fast_path_does_not_cache_retargeted_root(tmp_path, monkeypatch):
    from types import ModuleType
    import svx.cli

    package = ModuleType('pyslang')
    root, replacement = tmp_path / 'framework', tmp_path / 'replacement'
    root.mkdir()
    replacement.mkdir()
    (root / 'codec.py').write_text('VALUE = 1\n')
    (replacement / 'codec.py').write_text('VALUE = 2\n')
    source = (root / 'codec.py').resolve()
    package.__path__ = [str(root)]
    monkeypatch.setitem(sys.modules, 'pyslang', package)
    monkeypatch.setattr(svx.cli, '_STDLIB_SOURCE_ROOTS', ())
    # Remove unrelated package roots so only this canonical root is measured.
    for name in ('svx', 'svtypes'):
        monkeypatch.setattr(sys.modules[name], '__path__', [])
    with monkeypatch.context() as direct:
        resolved = []
        realpath = os.path.realpath
        def record_resolution(value, *args, **kwargs):
            resolved.append(os.fspath(value))
            return realpath(value, *args, **kwargs)
        direct.setattr(os.path, 'realpath', record_resolution)
        assert svx.cli._is_framework_source(source)
        assert resolved == [str(source)]
    retired = tmp_path / 'retired'
    root.rename(retired)
    root.symlink_to(replacement, target_is_directory=True)
    assert not svx.cli._is_framework_source((retired / 'codec.py').resolve())
    assert svx.cli._is_framework_source((root / 'codec.py').resolve())
    assert svx.cli._is_framework_source(source)
    package.__path__ = [str(root / '..' / root.name)]
    assert svx.cli._is_framework_source((replacement / 'codec.py').resolve())


def test_user_module_with_standard_library_name_remains_audited(tmp_path):
    (tmp_path / 'colorsys.py').write_text('USER_VALUE = 8\n')
    (tmp_path / 'stdlib_owner.py').write_text(
        source_text().replace('import svtypes\n', 'import colorsys\nimport svtypes\n'))
    manifest = tmp_path / 'generated' / 'manifest.json'
    args = ('inheritance-manifest', '--python-module', 'stdlib_owner', '--out', str(manifest))
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    record = json.loads(manifest.with_name(manifest.name + '.svx-discovery.json').read_text())
    assert {item['path'] for item in record['sources']} == {'../stdlib_owner.py', '../colorsys.py'}
    baseline = snapshot(manifest.parent)
    (tmp_path / 'colorsys.py').write_text('USER_VALUE = 9\n')
    result = run_cli(tmp_path, *args, '--check')
    assert result.returncode != 0, result.stderr
    assert snapshot(manifest.parent) == baseline


def test_explicit_standard_library_source_still_has_generation_fingerprint(tmp_path):
    import colorsys
    from tests.integration.sv_field_mirror_schema import manifest_data

    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(manifest_data()))
    generated = tmp_path / 'generated'
    args = ('inheritance-gen', '--manifest', str(manifest), '--python-source', colorsys.__file__,
            '--python-out', str(generated / 'python'), '--sv-out', str(generated / 'mirrors.sv'),
            '--artifact-manifest', str(generated / 'artifacts.json'))
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    inputs = json.loads((generated / 'artifacts.json').read_text())['generation_inputs']['python_sources']
    assert len(inputs) == 1
    assert (generated / inputs[0]['path']).resolve() == Path(colorsys.__file__).resolve()


def snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob('*') if path.is_file()}


def test_fresh_generation_tracks_macro_selected_headers_and_search_order(tmp_path):
    from tests.integration.sv_field_mirror_schema import manifest_data

    outputs = tmp_path / 'generated'
    outputs.mkdir()
    manifest = outputs / 'manifest.json'
    manifest.write_text(json.dumps(manifest_data()))
    source = tmp_path / 'source.sv'
    source.write_text('`define HEADER "owner.svh"\n`include `HEADER\n')
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    text = 'module owner; endmodule\n'
    (first / 'owner.svh').write_text(text)
    (second / 'owner.svh').write_text(text)
    generation = ('inheritance-gen', '--manifest', str(manifest),
                  '--sv-source', str(source), '--sv-include-dir', str(first),
                  '--sv-include-dir', str(second), '--python-out', str(outputs / 'python'),
                  '--sv-out', str(outputs / 'mirrors.sv'),
                  '--artifact-manifest', str(outputs / 'artifacts.json'))
    result = run_cli(tmp_path, *generation)
    assert result.returncode == 0, result.stderr
    baseline = snapshot(outputs)
    inputs = json.loads((outputs / 'artifacts.json').read_text())['generation_inputs']
    assert {item['path'] for item in inputs['sv_dependencies']} == {
        '../source.sv', '../first/owner.svh'}

    # Unselected search candidates do not invalidate the current compilation.
    (second / 'owner.svh').write_text(text + '// unselected edit\n')
    result = run_cli(tmp_path, *generation, '--check')
    assert result.returncode == 0, result.stderr
    assert snapshot(outputs) == baseline

    # Removing the selected candidate changes the graph even if its replacement
    # has exactly the old bytes. Both checking and refresh use real fresh parses.
    (second / 'owner.svh').write_text(text)
    (first / 'owner.svh').unlink()
    stale = run_cli(tmp_path, *generation, '--check')
    assert stale.returncode != 0
    assert 'sv_dependencies: added "../second/owner.svh"' in stale.stderr
    assert 'sv_dependencies: removed "../first/owner.svh"' in stale.stderr
    assert snapshot(outputs) == baseline
    refreshed = run_cli(tmp_path, *generation)
    assert refreshed.returncode == 0, refreshed.stderr
    current = snapshot(outputs)
    assert {name: value for name, value in current.items() if name != 'artifacts.json'} == {
        name: value for name, value in baseline.items() if name != 'artifacts.json'}
    assert run_cli(tmp_path, *generation, '--check').returncode == 0


def test_fresh_discovery_and_generation_distinguish_body_and_contract_edits(tmp_path):
    source = tmp_path / 'iteration_driver.py'
    source.write_text(source_text())
    outputs = tmp_path / 'generated'
    outputs.mkdir()
    discovery = ('inheritance-manifest', '--python-module', 'iteration_driver',
                 '--python-source', str(source), '--out', str(outputs / 'manifest.json'))
    generation = ('inheritance-gen', '--manifest', str(outputs / 'manifest.json'),
                  '--python-source', str(source), '--python-out', str(outputs / 'python'),
                  '--sv-out', str(outputs / 'mirrors.sv'),
                  '--artifact-manifest', str(outputs / 'artifacts.json'))
    for args in (discovery, generation, discovery + ('--check',), generation + ('--check',)):
        result = run_cli(tmp_path, *args)
        assert result.returncode == 0, result.stderr
    baseline = snapshot(outputs)

    source.write_text(source_text(result=2))
    assert run_cli(tmp_path, *discovery, '--check').returncode != 0
    stale = run_cli(tmp_path, *generation, '--check')
    assert stale.returncode != 0
    assert 'discovery source changed' in stale.stderr
    assert snapshot(outputs) == baseline
    assert run_cli(tmp_path, *discovery).returncode == 0
    assert run_cli(tmp_path, *generation).returncode == 0
    refreshed = snapshot(outputs)
    assert refreshed['artifacts.json'][0] != baseline['artifacts.json'][0]
    changed_records = {'artifacts.json', 'manifest.json.svx-discovery.json'}
    assert {name: value for name, value in refreshed.items() if name not in changed_records} == {
        name: value for name, value in baseline.items() if name not in changed_records}

    source.write_text(source_text(result=2, parameter=True))
    stale = run_cli(tmp_path, *discovery, '--check')
    assert stale.returncode != 0
    assert 'manifest is stale' in stale.stderr
    assert snapshot(outputs) == refreshed
    # Generation cannot certify an old contract against changed discovery sources.
    assert run_cli(tmp_path, *generation).returncode != 0
    assert run_cli(tmp_path, *generation, '--check').returncode != 0
    assert snapshot(outputs) == refreshed
    assert run_cli(tmp_path, *discovery, '--check').returncode != 0
    assert run_cli(tmp_path, *discovery).returncode == 0
    stale = run_cli(tmp_path, *generation, '--check')
    assert stale.returncode != 0
    assert run_cli(tmp_path, *generation).returncode == 0
    for args in (discovery + ('--check',), generation + ('--check',)):
        result = run_cli(tmp_path, *args)
        assert result.returncode == 0, result.stderr
    final = snapshot(outputs)
    assert final['manifest.json'][0] != baseline['manifest.json'][0]
    assert final['mirrors.sv'][0] != baseline['mirrors.sv'][0]
    assert final['python/.svx-generated-python.json'] == baseline['python/.svx-generated-python.json']


def test_body_edit_without_explicit_sources_refreshes_only_provenance(tmp_path):
    source = tmp_path / 'iteration_driver.py'
    source.write_text(source_text())
    outputs = tmp_path / 'generated'
    outputs.mkdir()
    discovery = ('inheritance-manifest', '--python-module', 'iteration_driver',
                 '--out', str(outputs / 'manifest.json'))
    generation = ('inheritance-gen', '--manifest', str(outputs / 'manifest.json'),
                  '--python-out', str(outputs / 'python'),
                  '--sv-out', str(outputs / 'mirrors.sv'),
                  '--artifact-manifest', str(outputs / 'artifacts.json'))
    for args in (discovery, generation):
        result = run_cli(tmp_path, *args)
        assert result.returncode == 0, result.stderr
    baseline = snapshot(outputs)

    source.write_text(source_text(result=2))
    for args in (discovery, generation):
        result = run_cli(tmp_path, *args, '--check')
        assert result.returncode != 0, result.stderr
    assert snapshot(outputs) == baseline
    for args in (discovery, generation):
        result = run_cli(tmp_path, *args)
        assert result.returncode == 0, result.stderr
    refreshed = snapshot(outputs)
    changed_records = {'artifacts.json', 'manifest.json.svx-discovery.json'}
    assert {name: value for name, value in refreshed.items() if name not in changed_records} == {
        name: value for name, value in baseline.items() if name not in changed_records}

    source.write_text(source_text(result=2, parameter=True))
    stale = run_cli(tmp_path, *discovery, '--check')
    assert stale.returncode != 0
    assert 'manifest is stale' in stale.stderr
    assert snapshot(outputs) == refreshed


def test_discovery_reads_same_size_entry_edit_despite_valid_timestamp_bytecode(tmp_path):
    source = tmp_path / 'iteration_driver.py'
    source.write_text(source_text())
    output = tmp_path / 'manifest.json'
    args = ('inheritance-manifest', '--python-module', 'iteration_driver', '--out', str(output))
    initial_stat = source.stat()
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    py_compile.compile(str(source), doraise=True)
    source.write_text(source_text().replace('calculate', 'increment'))
    os.utime(source, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))
    assert source.stat().st_size == initial_stat.st_size
    result = run_cli(tmp_path, *args, '--check')
    assert result.returncode != 0, 'fresh CLI silently accepted cached entry declarations'
    assert 'manifest is stale' in result.stderr
    assert output.read_bytes() == original
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert b'increment' in output.read_bytes()
    assert b'calculate' not in output.read_bytes()


def test_source_import_failure_restores_importers_and_module_state(tmp_path, monkeypatch):
    import pytest

    name = 'svx_iteration_failing_entry'
    (tmp_path / (name + '.py')).write_text('raise RuntimeError("entry failure")\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    before = list(sys.meta_path)
    with pytest.raises(RuntimeError, match='entry failure'):
        with _fresh_declaration_entries([name]):
            importlib.import_module(name)
    assert sys.meta_path == before
    assert name not in sys.modules


def test_discovery_does_not_reload_already_imported_entry(tmp_path, monkeypatch):
    name = 'svx_iteration_cached_entry'
    source = tmp_path / (name + '.py')
    source.write_text('value = 1\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        original = importlib.import_module(name)
        source.write_text('raise RuntimeError("cached entry must not reload")\n')
        with _fresh_declaration_entries([name]):
            loaded = importlib.import_module(name)
        assert loaded is original
        assert loaded.value == 1
    finally:
        sys.modules.pop(name, None)


def test_explicit_helper_source_edit_bypasses_old_bytecode(tmp_path):
    entry = tmp_path / 'iteration_driver.py'
    entry.write_text(source_text().replace('import svtypes', 'import svtypes\nimport iteration_types')
                     .replace('svtypes.Int', 'iteration_types.Value'))
    helper = tmp_path / 'iteration_types.py'
    helper.write_text('import svtypes\nValue = svtypes.Bit[8]\n')
    output = tmp_path / 'manifest.json'
    args = ('inheritance-manifest', '--python-module', 'iteration_driver',
            '--python-source', str(helper), '--out', str(output))
    initial = helper.stat()
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    py_compile.compile(str(helper), doraise=True)
    helper.write_text('import svtypes\nValue = svtypes.Bit[9]\n')
    os.utime(helper, ns=(initial.st_atime_ns, initial.st_mtime_ns))
    result = run_cli(tmp_path, *args, '--check')
    assert result.returncode != 0, 'explicit helper read stale declarations from pyc'
    assert 'manifest is stale' in result.stderr
    assert output.read_bytes() == original


def test_transitive_helper_source_edit_needs_no_explicit_dependency_list(tmp_path):
    entry = tmp_path / 'iteration_driver.py'
    entry.write_text(source_text().replace('import svtypes', 'import svtypes\nimport iteration_types')
                     .replace('svtypes.Int', 'iteration_types.Value'))
    helper = tmp_path / 'iteration_types.py'
    helper.write_text('import svtypes\nValue = svtypes.Bit[8]\n')
    output = tmp_path / 'manifest.json'
    args = ('inheritance-manifest', '--python-module', 'iteration_driver', '--out', str(output))
    initial = helper.stat()
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    before = output.read_bytes(), output.stat().st_mtime_ns
    py_compile.compile(str(helper), doraise=True)
    helper.write_text('import svtypes\nValue = svtypes.Bit[9]\n')
    os.utime(helper, ns=(initial.st_atime_ns, initial.st_mtime_ns))
    assert helper.stat().st_size == initial.st_size
    result = run_cli(tmp_path, *args, '--check')
    assert result.returncode != 0, 'transitive helper change was hidden by cached bytecode'
    assert 'manifest is stale' in result.stderr
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() != before[0]
    assert run_cli(tmp_path, *args, '--check').returncode == 0


def test_transitive_helper_edit_during_import_cannot_publish_manifest(tmp_path):
    entry = tmp_path / 'iteration_driver.py'
    entry.write_text(source_text().replace('import svtypes', 'import svtypes\nimport iteration_types')
                     .replace('svtypes.Int', 'iteration_types.Value'))
    helper = tmp_path / 'iteration_types.py'
    helper.write_text('import svtypes\nValue = svtypes.Bit[8]\nfrom pathlib import Path\n'
                      'p = Path(__file__)\np.write_text(p.read_text() + "# edit\\n")\n')
    output = tmp_path / 'manifest.json'
    output.write_text('previous manifest\n')
    before = output.read_bytes(), output.stat().st_mtime_ns
    result = run_cli(tmp_path, 'inheritance-manifest', '--python-module',
                     'iteration_driver', '--out', str(output))
    assert result.returncode != 0, 'transitive import mutation was accepted'
    assert 'manifest inputs changed during discovery' in result.stderr
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_discovery_cannot_overwrite_transitive_helper(tmp_path):
    entry = tmp_path / 'iteration_driver.py'
    entry.write_text(source_text().replace('import svtypes', 'import svtypes\nimport iteration_types'))
    helper = tmp_path / 'iteration_types.py'
    helper.write_text('Value = 8\n')
    before = helper.read_bytes(), helper.stat().st_mtime_ns
    result = run_cli(tmp_path, 'inheritance-manifest', '--python-module',
                     'iteration_driver', '--out', str(helper))
    assert result.returncode != 0, 'discovery overwrote an imported source dependency'
    assert 'input source' in result.stderr
    assert (helper.read_bytes(), helper.stat().st_mtime_ns) == before


def test_nested_source_imports_are_tracked_without_replacing_custom_importers(tmp_path, monkeypatch):
    entry_name = 'svx_iteration_transitive_entry'
    helper_name = 'svx_iteration_transitive_helper'
    foreign_name = 'svx_iteration_custom_helper'
    entry = tmp_path / (entry_name + '.py')
    helper = tmp_path / (helper_name + '.py')
    foreign = tmp_path / (foreign_name + '.py')
    entry.write_text(f'import {helper_name}\nvalue = {helper_name}.value\n')
    helper.write_text(f'import {foreign_name}\nvalue = {foreign_name}.value\n')
    foreign.write_text('raise RuntimeError("custom importer must win")\n')

    class Loader:
        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.value = 42

    class Finder:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == foreign_name:
                return importlib.machinery.ModuleSpec(fullname, Loader())
            return None

    finder = Finder()
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, 'meta_path', [finder, *sys.meta_path])
    before = list(sys.meta_path)
    for all_sources in (False, True):
        try:
            with _fresh_declaration_entries([entry_name], all_sources=all_sources) as consumed:
                module = importlib.import_module(entry_name)
            assert module.value == 42
            assert entry.resolve() in consumed and helper.resolve() in consumed
            assert foreign.resolve() not in consumed
            assert sys.meta_path == before
        finally:
            for name in (entry_name, helper_name, foreign_name):
                sys.modules.pop(name, None)


def late_codec_inputs(root, helper_text='VALUE = 8\n'):
    from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION
    from tests.integration.sv_field_mirror_schema import manifest_data

    declaration = manifest_data()['classes'][0]
    declaration['methods'] = []
    binding = declaration['fields'][0]['type']
    binding.pop('svtypes')
    binding['python'] = {'module': 'iteration_factory', 'symbol': 'make'}
    sidecar = root / 'declarations.json'
    sidecar.write_text(json.dumps({'schema_uri': SV_DECLARATION_SCHEMA_URI,
                                  'schema_version': SV_DECLARATION_SCHEMA_VERSION,
                                  'classes': [declaration]}))
    (root / 'iteration_factory.py').write_text(
        'import svtypes\ndef make():\n    import iteration_late_helper\n'
        '    print("LATE_VALUE=" + str(iteration_late_helper.VALUE))\n    return svtypes.Int()\n')
    helper = root / 'iteration_late_helper.py'
    helper.write_text(helper_text)
    return sidecar, helper


def test_late_codec_import_reads_current_source_without_explicit_dependency_list(tmp_path):
    sidecar, helper = late_codec_inputs(tmp_path)
    output = tmp_path / 'manifest.json'
    args = ('inheritance-manifest', '--sv-declarations', str(sidecar), '--out', str(output))
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    before = output.read_bytes(), output.stat().st_mtime_ns
    initial = helper.stat()
    py_compile.compile(str(helper), doraise=True)
    helper.write_text('VALUE = 9\n')
    os.utime(helper, ns=(initial.st_atime_ns, initial.st_mtime_ns))
    result = run_cli(tmp_path, *args, '--check')
    assert result.returncode != 0, result.stderr
    assert 'discovery provenance is stale' in result.stderr
    assert 'LATE_VALUE=9' in result.stdout, 'late codec factory used stale helper bytecode'
    assert 'LATE_VALUE=8' not in result.stdout
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    assert run_cli(tmp_path, *args).returncode == 0
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    assert run_cli(tmp_path, *args, '--check').returncode == 0


def test_late_codec_import_mutation_cannot_publish_manifest(tmp_path):
    sidecar, _helper = late_codec_inputs(tmp_path, 'VALUE = 8\nfrom pathlib import Path\n'
                                        'p = Path(__file__)\np.write_text(p.read_text() + "# edit\\n")\n')
    output = tmp_path / 'manifest.json'
    output.write_text('previous manifest\n')
    before = output.read_bytes(), output.stat().st_mtime_ns
    result = run_cli(tmp_path, 'inheritance-manifest', '--sv-declarations', str(sidecar),
                     '--out', str(output))
    assert result.returncode != 0, 'late codec mutation was accepted'
    assert 'manifest inputs changed during discovery' in result.stderr
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_discovery_cannot_overwrite_late_codec_helper(tmp_path):
    sidecar, helper = late_codec_inputs(tmp_path)
    before = helper.read_bytes(), helper.stat().st_mtime_ns
    result = run_cli(tmp_path, 'inheritance-manifest', '--sv-declarations', str(sidecar),
                     '--out', str(helper))
    assert result.returncode != 0, 'discovery overwrote a late codec source dependency'
    assert 'input source' in result.stderr
    assert (helper.read_bytes(), helper.stat().st_mtime_ns) == before


def late_generation_inputs(root):
    sidecar, helper = late_codec_inputs(root)
    outputs = root / 'generated'
    outputs.mkdir()
    manifest = outputs / 'manifest.json'
    result = run_cli(root, 'inheritance-manifest', '--sv-declarations', str(sidecar),
                     '--out', str(manifest))
    assert result.returncode == 0, result.stderr
    # This fixture isolates generation-only auditing of a handwritten contract.
    # Source-discovered cross-stage evidence is exercised by the dedicated probe.
    data = json.loads(manifest.read_text())
    data.pop('discovery_provenance')
    manifest.write_text(json.dumps(data))
    generation = ('inheritance-gen', '--manifest', str(manifest),
                  '--python-out', str(outputs / 'python'), '--sv-out', str(outputs / 'mirrors.sv'),
                  '--artifact-manifest', str(outputs / 'artifacts.json'))
    return helper, outputs, generation


def test_generation_late_codec_import_reads_current_source_without_refresh(tmp_path):
    helper, outputs, generation = late_generation_inputs(tmp_path)
    result = run_cli(tmp_path, *generation)
    assert result.returncode == 0, result.stderr
    before = snapshot(outputs)
    initial = helper.stat()
    py_compile.compile(str(helper), doraise=True)
    helper.write_text('VALUE = 9\n')
    os.utime(helper, ns=(initial.st_atime_ns, initial.st_mtime_ns))
    result = run_cli(tmp_path, *generation, '--check')
    assert result.returncode != 0, 'automatic codec source edit was not audited'
    assert 'iteration_late_helper.py' in result.stderr
    assert 'LATE_VALUE=9' in result.stdout, 'generation factory used stale helper bytecode'
    assert 'LATE_VALUE=8' not in result.stdout
    assert snapshot(outputs) == before
    result = run_cli(tmp_path, *generation)
    assert result.returncode == 0, result.stderr
    after = snapshot(outputs)
    for path, previous in before.items():
        if Path(path).name != 'artifacts.json':
            assert after[path] == previous
    assert run_cli(tmp_path, *generation, '--check').returncode == 0


def test_generation_prunes_removed_automatic_import_in_fresh_process(tmp_path):
    helper, outputs, generation = late_generation_inputs(tmp_path)
    result = run_cli(tmp_path, *generation)
    assert result.returncode == 0, result.stderr
    artifact = outputs / 'artifacts.json'
    records = json.loads(artifact.read_text())['generation_inputs']['python_imports']
    assert any(item['path'].endswith(helper.name) for item in records)
    (tmp_path / 'iteration_factory.py').write_text('import svtypes\ndef make(): return svtypes.Int()\n')
    helper.unlink()
    result = run_cli(tmp_path, *generation)
    assert result.returncode == 0, result.stderr
    records = json.loads(artifact.read_text())['generation_inputs']['python_imports']
    assert not any(item['path'].endswith(helper.name) for item in records)
    assert run_cli(tmp_path, *generation, '--check').returncode == 0


def test_generation_late_codec_import_mutation_cannot_publish_outputs(tmp_path):
    helper, outputs, generation = late_generation_inputs(tmp_path)
    before = snapshot(outputs)
    for flags in ((), ('--check',)):
        helper.write_text('VALUE = 8\nfrom pathlib import Path\n'
                          'p = Path(__file__)\np.write_text(p.read_text() + "# edit\\n")\n')
        result = run_cli(tmp_path, *generation, *flags)
        assert result.returncode != 0, 'generation accepted a mutating codec dependency'
        assert 'generation inputs changed during generation' in result.stderr
        assert snapshot(outputs) == before


def test_generation_late_codec_import_disappearance_preserves_outputs(tmp_path):
    helper, outputs, generation = late_generation_inputs(tmp_path)
    before = snapshot(outputs)
    helper.write_text('VALUE = 8\nfrom pathlib import Path\nPath(__file__).unlink()\n')
    result = run_cli(tmp_path, *generation)
    assert result.returncode != 0, 'generation accepted a deleted codec dependency'
    assert 'generation inputs could not be revalidated' in result.stderr
    assert snapshot(outputs) == before


def test_generation_cannot_overwrite_consumed_codec_helper_with_generated_marker(tmp_path):
    helper, outputs, generation = late_generation_inputs(tmp_path)
    helper.write_text('# Generated by svx inheritance-gen.\nVALUE = 8\n')
    before = snapshot(outputs)
    helper_before = helper.read_bytes(), helper.stat().st_mtime_ns
    result = run_cli(tmp_path, *generation, '--sv-out', str(helper))
    assert result.returncode != 0, 'generation overwrote a consumed codec source'
    assert 'input source' in result.stderr
    assert snapshot(outputs) == before
    assert (helper.read_bytes(), helper.stat().st_mtime_ns) == helper_before


def test_entry_imported_by_parent_during_spec_lookup_uses_current_source(tmp_path):
    package = tmp_path / 'iteration_package'
    package.mkdir()
    (package / '__init__.py').write_text('from . import driver\n')
    entry = package / 'driver.py'
    entry.write_text(source_text())
    output = tmp_path / 'manifest.json'
    args = ('inheritance-manifest', '--python-module', 'iteration_package.driver',
            '--out', str(output))
    initial = entry.stat()
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    py_compile.compile(str(entry), doraise=True)
    entry.write_text(source_text().replace('calculate', 'increment'))
    os.utime(entry, ns=(initial.st_atime_ns, initial.st_mtime_ns))
    result = run_cli(tmp_path, *args, '--check')
    assert result.returncode != 0, 'parent imported stale entry before freshness guard'
    assert 'manifest is stale' in result.stderr
    assert output.read_bytes() == original


def test_parent_import_cannot_hide_entry_self_edit_before_fingerprinting(tmp_path):
    package = tmp_path / 'iteration_package'
    package.mkdir()
    (package / '__init__.py').write_text('from . import driver\n')
    entry = package / 'driver.py'
    entry.write_text(source_text() + '\nfrom pathlib import Path\n'
                     'p = Path(__file__)\np.write_text(p.read_text() + "# self edit\\n")\n')
    output = tmp_path / 'manifest.json'
    output.write_text('previous manifest\n')
    before = output.read_bytes(), output.stat().st_mtime_ns
    args = ('inheritance-manifest', '--python-module', 'iteration_package.driver',
            '--out', str(output))
    result = run_cli(tmp_path, *args)
    assert result.returncode != 0, 'entry edit during parent spec lookup was accepted'
    assert 'manifest inputs changed during discovery' in result.stderr
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_discovery_cannot_overwrite_consumed_parent_package(tmp_path):
    package = tmp_path / 'iteration_package'
    package.mkdir()
    parent = package / '__init__.py'
    parent.write_text('from . import driver\n')
    (package / 'driver.py').write_text(source_text())
    before = parent.read_bytes(), parent.stat().st_mtime_ns
    result = run_cli(tmp_path, 'inheritance-manifest', '--python-module',
                     'iteration_package.driver', '--out', str(parent))
    assert result.returncode != 0
    assert 'input source' in result.stderr
    assert (parent.read_bytes(), parent.stat().st_mtime_ns) == before
