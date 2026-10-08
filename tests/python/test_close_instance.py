import pytest

from svx import SVXContextError, SVXInheritanceError, close_instance
from svx import _native


class Mirror:
    __svx_foreign_class_id__ = "sv://close_test/Base"
    _svx_remote_object_id = 17


def test_close_instance_accepts_a_bound_mirror_without_exposing_its_id(monkeypatch):
    value = Mirror()
    closed = []
    monkeypatch.setattr(_native, "inheritance_get", lambda _: value)
    monkeypatch.setattr(_native, "inheritance_close", closed.append)
    close_instance(value)
    assert closed == [17]


def test_close_instance_preserves_integer_keyword_and_repeated_close(monkeypatch):
    value = Mirror()
    bound = {17: value}
    closed = []
    monkeypatch.setattr(_native, "inheritance_get", bound.get)
    def close(object_id):
        closed.append(object_id)
        bound.pop(object_id, None)
    monkeypatch.setattr(_native, "inheritance_close", close)
    close_instance(value)
    close_instance(value)
    close_instance(object_id=17)
    assert closed == [17, 17, 17]
    assert value._svx_remote_object_id == 17


def test_close_instance_cannot_release_a_different_bound_receiver(monkeypatch):
    calls = []
    monkeypatch.setattr(_native, "inheritance_get", lambda _: Mirror())
    monkeypatch.setattr(_native, "inheritance_close", calls.append)
    with pytest.raises(SVXInheritanceError, match="different instance"):
        close_instance(Mirror())
    assert not calls


@pytest.mark.parametrize("value", [True, False, 0, -1, 1 << 64])
def test_close_instance_rejects_invalid_id_without_native_call(monkeypatch, value):
    calls = []
    monkeypatch.setattr(_native, "inheritance_close", calls.append)
    with pytest.raises((TypeError, ValueError), match="object ID"):
        close_instance(value)
    assert not calls


@pytest.mark.parametrize("value", [None, "17", object()])
def test_close_instance_rejects_non_mirror_objects(monkeypatch, value):
    calls = []
    monkeypatch.setattr(_native, "inheritance_close", calls.append)
    with pytest.raises(TypeError, match="cross-language instance"):
        close_instance(value)
    assert not calls


def test_close_instance_keeps_cleanup_errors_and_native_context_checks(monkeypatch):
    value = Mirror()
    monkeypatch.setattr(_native, "inheritance_get", lambda _: None)
    def close(_):
        raise RuntimeError("cleanup or context failure")
    monkeypatch.setattr(_native, "inheritance_close", close)
    with pytest.raises(RuntimeError, match="cleanup or context failure"):
        close_instance(value)


def test_close_instance_is_allowed_in_function_callback(monkeypatch):
    from svx.callback_context import blocking_operations_disallowed
    calls = []
    value = Mirror()
    monkeypatch.setattr(_native, "inheritance_get", lambda _: value)
    monkeypatch.setattr(_native, "inheritance_close", calls.append)
    with blocking_operations_disallowed("executing SV function callback close_test.check"):
        close_instance(value)
    assert calls == [17]


def test_function_cleanup_guard_covers_hook_and_restores_context():
    from svx.callback_context import _release_in_function_context, require_blocking_operations_allowed
    class Waiting:
        def _svx_release_projected_fields(self):
            require_blocking_operations_allowed("delay()")
    with pytest.raises(SVXContextError, match="delay.*SV function object cleanup"):
        _release_in_function_context(Waiting())
    require_blocking_operations_allowed("delay()")


def test_function_cleanup_guard_covers_descriptor_lookup():
    from svx.callback_context import _release_in_function_context, require_blocking_operations_allowed
    class Waiting:
        @property
        def _svx_release_projected_fields(self):
            require_blocking_operations_allowed("delay()")
    with pytest.raises(SVXContextError, match="SV function object cleanup"):
        _release_in_function_context(Waiting())


def test_function_cleanup_supports_fieldless_instances():
    from svx.callback_context import _release_in_function_context
    _release_in_function_context(object())
