import pytest

from svtypes import ExternalStorageError
import svx.inheritance as inheritance
from tests.python.test_early_receiver_reservation import reserved_environment
from tests.python.test_python_root_owner import Root, RootCompanion


@pytest.fixture
def literal_environment(reserved_environment, monkeypatch):
    _, _, bindings, transport = reserved_environment
    class_id = 'sv://literal/A'
    fields = {'count': class_id + '.count'}
    monkeypatch.setattr(RootCompanion, '__svx_foreign_class_id__', class_id, raising=False)
    monkeypatch.setattr(RootCompanion, '__svx_direct_mirror_field_ids__', fields, raising=False)
    inheritance.register_python_subclass(class_id, RootCompanion)
    return class_id, bindings, transport


def test_literal_reservation_keeps_one_receiver_without_user_init(literal_environment):
    class_id, bindings, _ = literal_environment
    inheritance._reserve_python_receiver(class_id, 91)
    value = bindings[91]
    retained = value.count
    inheritance._reserve_python_receiver(class_id, 91)
    assert bindings[91] is value and not Root.observations
    inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + class_id, 91, b'')
    assert value.count is retained and retained.value == 19
    assert value.local.value == 0 and not Root.observations
    assert not inheritance._reserved_python_receivers
    assert inheritance._pending_python_root.get() is None


def test_literal_collision_does_not_retire_existing_binding(literal_environment):
    class_id, bindings, _ = literal_environment
    original = object()
    bindings[91] = original
    with pytest.raises(inheritance.SVXInheritanceError, match='already bound'):
        inheritance._reserve_python_receiver(class_id, 91)
    assert bindings == {91: original} and not inheritance._reserved_python_receivers


def test_literal_early_close_cannot_silently_finish_initialization(literal_environment):
    class_id, bindings, _ = literal_environment
    inheritance._reserve_python_receiver(class_id, 91)
    value = bindings.pop(91)
    retained = value.count
    value._svx_release_projected_fields()
    assert not inheritance._reserved_python_receivers
    with pytest.raises(inheritance.SVXInheritanceError, match='literal constructor receiver is retired or missing'):
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + class_id, 91, b'')
    assert not Root.observations
    with pytest.raises(ExternalStorageError):
        _ = retained.value


def test_nested_literal_receiver_does_not_steal_outer_direct_owner(literal_environment):
    class_id, bindings, _ = literal_environment
    outer = RootCompanion.__new__(RootCompanion)
    pending = inheritance._PendingPythonRoot(outer, class_id, expected_object_id=90,
                                             direct_field_ids={'count': class_id + '.count'})
    token = inheritance._pending_python_root.set(pending)
    try:
        inheritance._reserve_python_receiver(class_id, 91)
        assert bindings[91] is not outer and pending.object_id is None
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + class_id, 91, b'')
        assert inheritance._pending_python_root.get() is pending
        assert not pending.initialized and pending.object_id is None
        assert not inheritance._reserved_python_receivers and not Root.observations
    finally:
        inheritance._pending_python_root.reset(token)


def test_literal_reservation_requires_own_generated_metadata(literal_environment, monkeypatch):
    class_id, bindings, _ = literal_environment
    monkeypatch.delattr(RootCompanion, '__svx_direct_mirror_field_ids__')
    with pytest.raises(inheritance.SVXInheritanceError, match='generated constructor target'):
        inheritance._reserve_python_receiver(class_id, 91)
    assert not bindings
