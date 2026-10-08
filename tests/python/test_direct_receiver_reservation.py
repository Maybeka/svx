import ast
from pathlib import PurePosixPath

import pytest

from svtypes import ExternalStorageError
from svx import _native
from svx.declarations import SVMirror
import svx.inheritance as inheritance
from tests.python.test_early_receiver_reservation import reserved_environment
from tests.python.test_python_root_owner import Root, RootCompanion
from tests.integration.same_package_schema import manifest_data


def test_private_direct_generator_selects_only_physical_sv_base_fields():
    manifest = inheritance.parse_manifest(manifest_data())
    sources = inheritance._emit_sv_root_artifacts(manifest, source_managed_layout=True)
    text = sources[PurePosixPath('svx_mirror/same_package_pkg.py')]
    root = next(node for node in ast.parse(text).body if isinstance(node, ast.ClassDef) and node.name == 'A')
    initializer = next(node for node in root.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    create = next(node for node in ast.walk(initializer) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == '_create_sv_with_direct_mirror')
    assert ast.literal_eval(create.args[-1]) == {'count': 'sv://same_package_pkg/A.count'}
    public = inheritance.emit_python_mirrors(manifest, register_sv_subclasses=False,
                                              separate_package_layout=False)
    assert '_create_sv_with_direct_mirror' not in public[PurePosixPath('svx_mirror/same_package_pkg.py')]


def test_direct_generator_does_not_shadow_constructor_parameter():
    data = manifest_data()
    a, b = data['classes'][0]['base_lineage']
    parameter = {'name': '_create_sv_with_direct_mirror', 'type': a['fields'][0]['type']}
    for declaration in (a, b, data['classes'][0]):
        declaration['constructor']['parameters'] = [parameter]
    manifest = inheritance.parse_manifest(data)
    text = inheritance._emit_sv_root_artifacts(manifest, source_managed_layout=True)[
        PurePosixPath('svx_mirror/same_package_pkg.py')]
    root = next(node for node in ast.parse(text).body if isinstance(node, ast.ClassDef) and node.name == 'A')
    initializer = next(node for node in root.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    helper = next(node for node in ast.walk(initializer) if isinstance(node, ast.ImportFrom)
                  and node.names[0].name == '_create_sv_with_direct_mirror')
    assert helper.names[0].asname != '_create_sv_with_direct_mirror'
    compile(text, 'generated.py', 'exec')


def instance():
    value = RootCompanion.__new__(RootCompanion)
    SVMirror.__init__(value)
    return value


@pytest.mark.parametrize('early_callback', [False, True])
def test_direct_receiver_binds_original_owner_without_running_user_init(reserved_environment, monkeypatch, early_callback):
    root_id, _, bindings, _ = reserved_environment
    value = instance()
    local = value.local
    def create(class_id, payload):
        inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_EXPECT_PREFIX + class_id, 91, b'')
        if early_callback:
            inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_RESERVE_PREFIX + class_id, 91, b'')
            assert bindings[91] is value
            value.count.value = 21
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + class_id, 91, payload)
        assert bindings[91] is value
        return 91
    monkeypatch.setattr(_native, 'inheritance_create_sv', create)
    assert inheritance._create_sv_with_direct_mirror(value, root_id, b'', {'count': root_id + '.count'}) == 91
    assert value.count.value == (21 if early_callback else 19)
    assert value.local is local and local.value == 0
    assert not Root.observations
    assert value._svx_target_constructor_completed
    assert not inheritance._reserved_python_receivers
    assert inheritance._pending_python_root.get() is None


def test_direct_wrong_returned_id_rolls_back_both_ids_and_stales_views(reserved_environment, monkeypatch):
    root_id, _, bindings, _ = reserved_environment
    value = instance()
    closed = []
    views = []
    def create(class_id, payload):
        inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_RESERVE_PREFIX + class_id, 91, b'')
        views.append(value.count)
        return 92
    def close(object_id):
        closed.append(object_id)
        bindings.pop(object_id, None)
    monkeypatch.setattr(_native, 'inheritance_create_sv', create)
    monkeypatch.setattr(_native, 'inheritance_close', close)
    with pytest.raises(inheritance.SVXInheritanceError, match='did not complete'):
        inheritance._create_sv_with_direct_mirror(value, root_id, b'', {'count': root_id + '.count'})
    assert closed == [91, 92] and not bindings and not Root.observations
    with pytest.raises(ExternalStorageError):
        _ = views[0].value
    assert inheritance._pending_python_root.get() is None


def test_direct_exception_preserved_with_cleanup_error(reserved_environment, monkeypatch):
    root_id, _, bindings, _ = reserved_environment
    value = instance()
    error = ValueError('SV constructor failed')
    def create(class_id, payload):
        inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_RESERVE_PREFIX + class_id, 91, b'')
        raise error
    def close(object_id):
        bindings.pop(object_id, None)
        raise RuntimeError('native close failed')
    monkeypatch.setattr(_native, 'inheritance_create_sv', create)
    monkeypatch.setattr(_native, 'inheritance_close', close)
    with pytest.raises(ValueError, match='SV constructor failed') as caught:
        inheritance._create_sv_with_direct_mirror(value, root_id, b'', {'count': root_id + '.count'})
    assert caught.value is error
    assert any('native close failed' in note for note in error.__notes__)
    assert not bindings and inheritance._pending_python_root.get() is None


def test_direct_close_during_sv_base_construction_cannot_resume(reserved_environment, monkeypatch):
    root_id, _, bindings, _ = reserved_environment
    value = instance()
    def create(class_id, payload):
        inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_RESERVE_PREFIX + class_id, 91, b'')
        bindings.pop(91)._svx_release_projected_fields()
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + class_id, 91, payload)
        return 91
    monkeypatch.setattr(_native, 'inheritance_create_sv', create)
    monkeypatch.setattr(_native, 'inheritance_close', lambda key: bindings.pop(key, None))
    with pytest.raises(inheritance.SVXInheritanceError, match='retired'):
        inheritance._create_sv_with_direct_mirror(value, root_id, b'', {'count': root_id + '.count'})
    assert not bindings and not Root.observations
    assert inheritance._pending_python_root.get() is None
