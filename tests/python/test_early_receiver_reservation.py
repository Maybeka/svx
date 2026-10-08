import json

import pytest
from svtypes import CodecSession, ExternalStorageError, Int

import svx.inheritance as inheritance
from svx import runtime
from svx.declarations import _svtypes_binding
from tests.python.test_python_root_owner import Root, RootCompanion, Transport
from svx.field_storage import SVXFieldStorage


@pytest.fixture
def reserved_environment(monkeypatch):
    root_id = 'py://early/Root'
    Root.observations.clear()
    bindings = {}
    transport = Transport()
    monkeypatch.setattr(inheritance, '_constructor_contracts', {})
    monkeypatch.setattr(inheritance, '_python_subclasses', {})
    monkeypatch.setattr(inheritance, '_reserved_python_receivers', {})
    monkeypatch.setattr(runtime, '_state', runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, '_codec_session', CodecSession())
    monkeypatch.setattr('svx._native.inheritance_get', bindings.get)
    monkeypatch.setattr('svx._native.inheritance_bind', lambda key, value: bindings.__setitem__(key, value))
    monkeypatch.setattr('svx._native.inheritance_unbind', lambda key: bindings.pop(key))
    monkeypatch.setattr('svx.field_storage.SVXFieldStorage', lambda: SVXFieldStorage(transport))
    spec = inheritance._type_binding(_svtypes_binding(Int, where='early.seed'), 'early.seed',
                                     allow_void=False).runtime_spec()
    inheritance.register_constructor(root_id, (('seed', spec),))
    inheritance.register_python_subclass(root_id, RootCompanion)
    selector = inheritance._PYTHON_ROOT_ALLOC_PREFIX + json.dumps(
        {'root': root_id, 'target': root_id, 'portions': []})
    return root_id, selector, bindings, transport


def test_reservation_does_not_initialize_and_keeps_early_field_views(reserved_environment):
    root_id, selector, bindings, transport = reserved_environment
    inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_RESERVE_PREFIX + selector, 91, b'')
    instance = bindings[91]
    identity, backend, retained = instance.svtypes_object_number, instance._svx_field_storage, instance.count
    assert Root.observations == []
    assert retained.value == 19
    retained.value = 21
    inheritance._reserve_python_receiver(selector, 91)
    assert bindings[91] is instance
    payload = inheritance.encode_constructor(root_id, {'seed': 23})
    inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
    assert Root.observations == [(instance, 21)]
    assert retained.value == 23
    assert instance.svtypes_object_number == identity
    assert instance._svx_field_storage is backend
    assert instance.svtypes_auto_cov.instantiated
    assert not inheritance._reserved_python_receivers
    assert inheritance._pending_python_root.get() is None


def test_native_release_hook_retires_reserved_receiver_before_initialization(reserved_environment):
    root_id, selector, bindings, _ = reserved_environment
    inheritance._reserve_python_receiver(selector, 91)
    instance = bindings.pop(91)
    retained = instance.count
    instance._svx_release_projected_fields()
    assert not inheritance._reserved_python_receivers
    payload = inheritance.encode_constructor(root_id, {'seed': 23})
    with pytest.raises(inheritance.SVXInheritanceError, match='retired or missing'):
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + selector, 91, payload)
    assert not Root.observations
    with pytest.raises(ExternalStorageError):
        _ = retained.value


def test_pending_receiver_release_prevents_user_initialization(reserved_environment):
    root_id, selector, bindings, _ = reserved_environment
    instance = RootCompanion.__new__(RootCompanion)
    pending = inheritance._PendingPythonRoot(instance, root_id)
    token = inheritance._pending_python_root.set(pending)
    try:
        inheritance._reserve_python_receiver(selector, 91)
        bindings.pop(91)._svx_release_projected_fields()
        payload = inheritance.encode_constructor(root_id, {'seed': 23})
        with pytest.raises(inheritance.SVXInheritanceError, match='retired'):
            inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
        assert not pending.initialized and not Root.observations
    finally:
        inheritance._pending_python_root.reset(token)


def test_release_error_cannot_keep_reserved_reference(reserved_environment, monkeypatch):
    _, selector, bindings, _ = reserved_environment
    inheritance._reserve_python_receiver(selector, 91)
    instance = bindings.pop(91)
    def fail():
        raise RuntimeError('storage cleanup failed')
    monkeypatch.setattr(instance._svx_field_storage, 'close', fail)
    with pytest.raises(RuntimeError, match='storage cleanup failed'):
        instance._svx_release_projected_fields()
    assert not inheritance._reserved_python_receivers


def test_receiver_closed_inside_user_initializer_cannot_finish_construction(reserved_environment, monkeypatch):
    root_id, selector, bindings, _ = reserved_environment
    def close_in_initializer(self, seed):
        bindings.pop(91)._svx_release_projected_fields()
    monkeypatch.setattr(RootCompanion, '__init__', close_in_initializer)
    inheritance._reserve_python_receiver(selector, 91)
    payload = inheritance.encode_constructor(root_id, {'seed': 23})
    with pytest.raises(inheritance.SVXInheritanceError, match='retired during initialization'):
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
    assert not bindings and not inheritance._reserved_python_receivers
    assert inheritance._pending_python_root.get() is None


def test_unrelated_cleanup_does_not_retire_another_pending_receiver(reserved_environment):
    root_id, selector, bindings, _ = reserved_environment
    instance = RootCompanion.__new__(RootCompanion)
    pending = inheritance._PendingPythonRoot(instance, root_id)
    token = inheritance._pending_python_root.set(pending)
    try:
        inheritance._reserve_python_receiver(selector, 91)
        unrelated = RootCompanion.__new__(RootCompanion)
        unrelated._svx_release_projected_fields()
        assert not pending.retired
        payload = inheritance.encode_constructor(root_id, {'seed': 23})
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
        assert pending.initialized and bindings[91] is instance
    finally:
        inheritance._pending_python_root.reset(token)


@pytest.mark.parametrize('object_id', [0, -1, 1 << 64])
def test_reservation_rejects_invalid_id_before_binding(reserved_environment, object_id):
    _, selector, bindings, _ = reserved_environment
    with pytest.raises(inheritance.SVXInheritanceError, match='nonzero object ID'):
        inheritance._reserve_python_receiver(selector, object_id)
    assert not bindings and not Root.observations


def test_reserved_initializer_failure_unbinds_and_invalidates_views(reserved_environment, monkeypatch):
    root_id, selector, bindings, _ = reserved_environment
    monkeypatch.setattr(Root, 'fail', True)
    inheritance._reserve_python_receiver(selector, 91)
    retained = bindings[91].count
    payload = inheritance.encode_constructor(root_id, {'seed': 23})
    with pytest.raises(ValueError, match='root initialization failed'):
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
    assert not bindings and not inheritance._reserved_python_receivers
    assert inheritance._pending_python_root.get() is None
    with pytest.raises(ExternalStorageError):
        _ = retained.value


def test_reservation_reuses_pending_python_origin_receiver(reserved_environment):
    root_id, selector, bindings, _ = reserved_environment
    instance = RootCompanion.__new__(RootCompanion)
    pending = inheritance._PendingPythonRoot(instance, root_id)
    token = inheritance._pending_python_root.set(pending)
    try:
        inheritance._reserve_python_receiver(selector, 91)
        assert bindings[91] is instance and pending.object_id == 91
        assert not Root.observations and not inheritance._reserved_python_receivers
        payload = inheritance.encode_constructor(root_id, {'seed': 23})
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
        assert pending.initialized and Root.observations == [(instance, 19)]
    finally:
        inheritance._pending_python_root.reset(token)


def test_reservation_does_not_retire_an_existing_foreign_binding(reserved_environment):
    _, selector, bindings, _ = reserved_environment
    original = object()
    bindings[91] = original
    with pytest.raises(inheritance.SVXInheritanceError, match='already bound'):
        inheritance._reserve_python_receiver(selector, 91)
    assert bindings == {91: original} and not Root.observations


@pytest.mark.parametrize('suffix', ['{', '{}', '{"root": 3, "target": "py://early/Root", "portions": []}'])
def test_bad_reservation_metadata_rejected_before_binding(reserved_environment, suffix):
    _, _, bindings, _ = reserved_environment
    with pytest.raises(inheritance.SVXInheritanceError, match='invalid receiver reservation target'):
        inheritance._reserve_python_receiver(inheritance._PYTHON_ROOT_ALLOC_PREFIX + suffix, 91)
    assert not bindings and not Root.observations


def test_expected_id_separates_same_target_nested_receiver_before_outer_callback(reserved_environment):
    root_id, selector, bindings, transport = reserved_environment
    payloads = {91: Int().pack(19), 92: Int().pack(19)}
    transport.read_field = lambda object_id, *_: payloads[object_id]
    transport.write_field = lambda object_id, field_id, descriptor, path, operation, payload: payloads.__setitem__(object_id, payload)
    outer = RootCompanion.__new__(RootCompanion)
    pending = inheritance._PendingPythonRoot(outer, root_id, expected_class_id=root_id)
    token = inheritance._pending_python_root.set(pending)
    try:
        inheritance.create_python_instance(inheritance._PYTHON_RECEIVER_EXPECT_PREFIX + root_id, 91, b'')
        inheritance._reserve_python_receiver(selector, 92)
        inner = bindings[92]
        assert inner is not outer and pending.object_id is None
        payload = inheritance.encode_constructor(root_id, {'seed': 23})
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 92, payload)
        assert inheritance._pending_python_root.get() is pending and not pending.initialized
        inheritance._reserve_python_receiver(selector, 91)
        assert bindings[91] is outer
        payload = inheritance.encode_constructor(root_id, {'seed': 29})
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, payload)
        assert Root.observations == [(inner, 19), (outer, 19)]
        assert inner.count.value == 23 and outer.count.value == 29
        assert not inheritance._reserved_python_receivers
    finally:
        inheritance._pending_python_root.reset(token)


def test_factory_expectation_rejects_target_or_id_changes_without_binding(reserved_environment):
    root_id, _, bindings, _ = reserved_environment
    pending = inheritance._PendingPythonRoot(RootCompanion.__new__(RootCompanion), root_id,
                                             expected_class_id=root_id)
    token = inheritance._pending_python_root.set(pending)
    try:
        inheritance._expect_python_receiver(root_id, 91)
        with pytest.raises(inheritance.SVXInheritanceError, match='requested SV target'):
            inheritance._expect_python_receiver('sv://another/Target', 91)
        with pytest.raises(inheritance.SVXInheritanceError, match='changed the paired object ID'):
            inheritance._expect_python_receiver(root_id, 92)
        assert pending.expected_object_id == 91 and not bindings and not Root.observations
    finally:
        inheritance._pending_python_root.reset(token)


def test_internal_factory_announces_id_before_construction_only_when_requested():
    from tests.integration.same_package_schema import manifest_data
    source = inheritance.parse_manifest(manifest_data()).classes[0]
    text = '\n'.join(inheritance._emit_sv_projection_factory(source, 'Target', announce_receiver=True))
    assert text.index(inheritance._PYTHON_RECEIVER_EXPECT_PREFIX) < text.index('instance = new(')
    assert inheritance._PYTHON_RECEIVER_EXPECT_PREFIX not in '\n'.join(
        inheritance._emit_sv_projection_factory(source, 'Target'))
