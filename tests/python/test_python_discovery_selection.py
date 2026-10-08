import hashlib
import json

import pytest

from svx.discovery_provenance import discovery_contract_digest, validate_discovery_provenance
from svx.errors import SVXInheritanceError
from tests.integration.sv_field_mirror_schema import manifest_data


def evidence(root, selections, entries=(), namespaces=()):
    data = manifest_data()
    data['discovery_provenance'] = {'schema_version': '1.0.0', 'path': 'evidence.json'}
    manifest = root / 'manifest.json'
    manifest.write_text(json.dumps(data))
    paths = {item['path'] for item in selections}
    record = {'schema_version': '1.0.0', 'contract_sha256': discovery_contract_digest(data),
              'configuration': {'python_modules': list(entries), 'python_selections': selections,
                                'python_namespaces': list(namespaces)},
              'sources': [{'path': path, 'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()}
                          for path in sorted(paths)]}
    (root / 'evidence.json').write_text(json.dumps(record))
    return data, manifest, record


@pytest.mark.parametrize('namespace', [False, True])
def test_selection_resolves_packages_without_running_initializers(tmp_path, monkeypatch, namespace):
    package = tmp_path / 'selection_package'
    package.mkdir()
    selections = [{'module': 'selection_package.helper', 'path': 'selection_package/helper.py'}]
    if not namespace:
        (package / '__init__.py').write_text('raise AssertionError("initializer executed")\n')
        selections.append({'module': 'selection_package', 'path': 'selection_package/__init__.py'})
    (package / 'helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    namespaces = [{'module': 'selection_package', 'paths': ['selection_package']}] if namespace else []
    data, manifest, _ = evidence(tmp_path, selections, ('selection_package.helper',), namespaces)
    validate_discovery_provenance(data, manifest)
    preferred = tmp_path / 'preferred'
    other = preferred / 'selection_package'
    other.mkdir(parents=True)
    (other / '__init__.py').write_text('raise AssertionError("preferred initializer executed")\n')
    (other / 'helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(preferred))
    with pytest.raises(SVXInheritanceError, match='Python selection changed'):
        validate_discovery_provenance(data, manifest)


@pytest.mark.parametrize('damage', ['duplicate', 'missing_entry', 'missing_inventory', 'untracked'])
def test_bad_python_selection_records_reject(tmp_path, monkeypatch, damage):
    (tmp_path / 'selection_helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    selection = {'module': 'selection_helper', 'path': 'selection_helper.py'}
    data, manifest, record = evidence(tmp_path, [selection], ('selection_helper',))
    validate_discovery_provenance(data, manifest)
    config = record['configuration']
    if damage == 'duplicate':
        config['python_selections'].append(dict(selection))
    elif damage == 'missing_entry':
        config['python_selections'] = []
    elif damage == 'missing_inventory':
        config.pop('python_selections')
    else:
        config['python_selections'][0]['path'] = 'other.py'
    (tmp_path / 'evidence.json').write_text(json.dumps(record))
    with pytest.raises(SVXInheritanceError, match='Python.*inventory|Python entry selection'):
        validate_discovery_provenance(data, manifest)


def test_nested_namespace_resolution_without_cached_parents(tmp_path, monkeypatch):
    package = tmp_path / 'outer_selection' / 'inner_selection'
    package.mkdir(parents=True)
    (package / 'helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    data, manifest, _ = evidence(tmp_path, [{
        'module': 'outer_selection.inner_selection.helper',
        'path': 'outer_selection/inner_selection/helper.py'}], namespaces=[
            {'module': 'outer_selection', 'paths': ['outer_selection']},
            {'module': 'outer_selection.inner_selection', 'paths': ['outer_selection/inner_selection']}])
    validate_discovery_provenance(data, manifest)


def test_namespace_becoming_regular_package_invalidates_selection(tmp_path, monkeypatch):
    package = tmp_path / 'namespace_selection'
    package.mkdir()
    (package / 'helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    data, manifest, _ = evidence(tmp_path, [{
        'module': 'namespace_selection.helper', 'path': 'namespace_selection/helper.py'}],
        namespaces=[{'module': 'namespace_selection', 'paths': ['namespace_selection']}])
    validate_discovery_provenance(data, manifest)
    (package / '__init__.py').write_text('raise AssertionError("must not execute")\n')
    with pytest.raises(SVXInheritanceError, match='namespace selection changed'):
        validate_discovery_provenance(data, manifest)


@pytest.mark.parametrize('change', ['added_location', 'reordered_locations'])
def test_namespace_search_locations_are_ordered_inputs(tmp_path, monkeypatch, change):
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    for parent in (first, second):
        (parent / 'namespace_paths').mkdir(parents=True)
    (first / 'namespace_paths/helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(second))
    monkeypatch.syspath_prepend(str(first))
    data, manifest, _ = evidence(tmp_path, [{
        'module': 'namespace_paths.helper', 'path': 'first/namespace_paths/helper.py'}],
        namespaces=[{'module': 'namespace_paths', 'paths': [
            'first/namespace_paths', 'second/namespace_paths']}])
    validate_discovery_provenance(data, manifest)
    if change == 'added_location':
        third = tmp_path / 'third'
        (third / 'namespace_paths').mkdir(parents=True)
        monkeypatch.syspath_prepend(str(third))
    else:
        import sys
        monkeypatch.setattr(sys, 'path', [str(second), str(first), *sys.path[2:]])
    with pytest.raises(SVXInheritanceError, match='namespace selection changed'):
        validate_discovery_provenance(data, manifest)


def test_repeated_namespace_search_directory_is_not_a_selection_change(tmp_path, monkeypatch):
    (tmp_path / 'namespace_duplicate').mkdir()
    (tmp_path / 'namespace_duplicate/helper.py').write_text('VALUE = 8\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    data, manifest, _ = evidence(tmp_path, [{
        'module': 'namespace_duplicate.helper', 'path': 'namespace_duplicate/helper.py'}],
        namespaces=[{'module': 'namespace_duplicate', 'paths': ['namespace_duplicate']}])
    validate_discovery_provenance(data, manifest)
    monkeypatch.syspath_prepend(str(tmp_path))
    validate_discovery_provenance(data, manifest)
