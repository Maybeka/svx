from pathlib import PurePosixPath

from svx.inheritance import (
    _emit_python_root_artifacts, _emit_python_root_sv_packages, artifact_manifest, parse_manifest,
)
from tests.integration.python_root_namespace_schema import emit_sources, manifest_data


def test_root_packages_use_expected_names_without_private_fixture_aliases():
    packages = _emit_python_root_sv_packages(parse_manifest(manifest_data()), has_call_records=True)
    assert set(packages) == {
        'svx_proxy_python_root_proxy_test', 'svx_mirror_sv_python_root_probe_pkg_Child',
        'svx_proxy_python_root_derived', 'svx_mirror_sv_python_root_e_probe_pkg_Grandchild',
    }
    root = packages['svx_proxy_python_root_proxy_test']
    child = packages['svx_mirror_sv_python_root_probe_pkg_Child']
    assert 'class Root implements' in root and 'class PlainRoot implements' in root
    assert 'class Child extends python_root_probe_pkg::Child implements' in child
    assert 'class Child_factory implements svx_factory' in child
    assert 'DerivedProxy' not in root + child
    assert 'ChildMirror' not in root + child
    assert 'package python_root_probe_pkg;' not in root + child
    derived = packages['svx_proxy_python_root_derived']
    assert 'class Derived extends svx_mirror_sv_python_root_probe_pkg_Child::Child' in derived
    assert 'class DerivedProxy' not in derived


def test_root_packages_emit_only_requested_edges_not_every_ancestor_target():
    data = manifest_data()
    data['classes'] = data['classes'][3:4]
    manifest = parse_manifest(data)
    packages = _emit_python_root_sv_packages(manifest, has_call_records=True)
    assert len(manifest.classes) == 1
    text = '\n'.join(packages.values())
    assert 'class Root implements' in text and 'class Child extends' in text
    assert 'class PlainRoot' not in text
    assert 'class Derived' not in text
    assert 'class Grandchild' not in text


def test_root_metadata_includes_terminal_sv_views_in_their_emitted_modules():
    model, python, sources = emit_sources()
    metadata = artifact_manifest(model, python, sv_sources=sources, python_path_prefix='python')
    types = {item['canonical_class_id']: item for item in metadata['generated_types']}
    assert types['sv://python_root_e_probe_pkg/Grandchild']['python_fqn'] == (
        'svx_mirror.python_root_e_probe_pkg.Grandchild')
    assert types['py://tests/integration/python_root/Derived']['systemverilog_fqn'] == (
        'svx_proxy_python_root_derived::Derived')


def test_sv_origin_terminal_root_view_supports_python_allocation_and_sv_factory():
    data = manifest_data()
    data['classes'][-1]['constructor']['initiator'] = 'sv'
    manifest = parse_manifest(data)
    python = _emit_python_root_artifacts(manifest)
    view = next(text for path, text in python.items()
                if str(path) == 'svx_mirror/python_root_e_probe_pkg.py')
    assert 'class Grandchild(' in view
    assert "SV-initiated inheritance instances must be created by SV" not in view
    assert "_create_sv_with_python_root" in view
    packages = _emit_python_root_sv_packages(manifest, has_call_records=True)
    helper = packages['svx_mirror_sv_python_root_e_probe_pkg_Grandchild']
    assert 'class Grandchild extends python_root_e_probe_pkg::Grandchild' in helper
    assert 'class Grandchild_factory' in helper
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources={
        PurePosixPath(name + '.svh'): text for name, text in packages.items()
    })
    types = {item['canonical_class_id']: item for item in metadata['generated_types']}
    assert types['sv://python_root_e_probe_pkg/Grandchild']['python_fqn'] == (
        'svx_mirror.python_root_e_probe_pkg.Grandchild')


def test_direct_sv_initiated_target_keeps_root_and_terminal_view_only():
    data = manifest_data()
    data['classes'] = data['classes'][2:3]
    data['classes'][0]['constructor']['initiator'] = 'sv'
    manifest = parse_manifest(data)
    packages = _emit_python_root_sv_packages(manifest, has_call_records=True)
    assert set(packages) == {
        'svx_proxy_python_root_proxy_test', 'svx_mirror_sv_python_root_probe_pkg_Child',
    }
    python = _emit_python_root_artifacts(manifest)
    assert any(str(path) == 'svx_mirror/python_root_probe_pkg.py' for path in python)
def test_python_root_companions_keep_callback_boundaries_for_every_sv_ancestor():
    import ast
    from svx.inheritance import _emit_python_root_companion
    from tests.integration.python_root_proxy_schema import probe_manifest_data, ROOT_ID, DERIVED_ID

    model = parse_manifest(probe_manifest_data())
    by_id = {source.canonical_id: source for source in model.classes}
    for target_id, expected in (
        (DERIVED_ID, {ROOT_ID: ROOT_ID,
                      'sv://python_root_probe_pkg/Child': DERIVED_ID}),
        ('py://tests/integration/python_root/Final', {
            ROOT_ID: ROOT_ID, DERIVED_ID: DERIVED_ID,
            'sv://python_root_probe_pkg/Child': DERIVED_ID,
            'sv://python_root_probe_pkg/Grandchild': 'py://tests/integration/python_root/Final'}),
    ):
        source = by_id[target_id]
        ancestors = tuple(by_id[item.canonical_id] for item in source.base_lineage)
        tree = ast.parse(_emit_python_root_companion(model, source, ancestor_sources=ancestors))
        generated = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        actual = next(ast.literal_eval(node.value) for node in generated.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name)
                              and target.id == '__svx_python_callback_portions__'
                              for target in node.targets))
        assert actual == expected
