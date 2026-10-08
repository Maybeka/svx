import inspect

import pytest

from svx.declarations import SVMirror


@pytest.fixture
def guarded(monkeypatch):
    import svx.inheritance as inheritance

    events = []
    captured = []

    class Base(SVMirror):
        __svx_guard_descendant_initializers__ = True

        def __init__(self, seed: int = 4):
            super().__init__()
            if self._svx_remote_object_id is None:
                self._svx_bind_remote_object(seed)
            self._svx_target_constructor_completed = True
            captured.append(self)

        def _svx_release_projected_fields(self):
            events.append(('storage', self))

    class Derived(Base):
        def __init__(self, seed: int = 4):
            super().__init__(seed)
            raise ValueError('outer initializer failed')

    monkeypatch.setattr(inheritance, 'close_instance', lambda owner: events.append(('target', owner)))
    return Base, Derived, captured, events


def test_outer_failure_rolls_back_once_after_nested_super_and_preserves_signature(guarded):
    Base, Derived, captured, events = guarded
    with pytest.raises(ValueError, match='outer initializer failed'):
        Derived(91)
    owner = captured[0]
    assert events == [('storage', owner), ('target', owner)]
    assert owner._svx_initializer_depth == 0
    for cls in (Base, Derived):
        assert inspect.signature(cls.__init__) == inspect.signature(inspect.unwrap(cls.__init__))
        assert list(inspect.signature(cls.__init__).parameters) == ['self', 'seed']


def test_reinitializing_existing_receiver_does_not_retire_it(guarded):
    _, Derived, captured, events = guarded
    owner = Derived.__new__(Derived)
    owner._svx_bind_remote_object(91)
    with pytest.raises(ValueError, match='outer initializer failed'):
        Derived.__init__(owner, 91)
    assert captured == [owner]
    assert events == []
    assert owner._svx_initializer_depth == 0


def test_cleanup_failures_are_independent_notes_on_original_error(guarded, monkeypatch):
    import svx.inheritance as inheritance
    Base, Derived, captured, events = guarded

    def storage(owner):
        events.append(('storage', owner))
        raise RuntimeError('storage cleanup failed')

    def target(owner):
        events.append(('target', owner))
        raise RuntimeError('target cleanup failed')

    monkeypatch.setattr(Base, '_svx_release_projected_fields', storage)
    monkeypatch.setattr(inheritance, 'close_instance', target)
    with pytest.raises(ValueError, match='outer initializer failed') as caught:
        Derived(91)
    assert events == [('storage', captured[0]), ('target', captured[0])]
    assert any('storage cleanup failed' in note for note in caught.value.__notes__)
    assert any('target cleanup failed' in note for note in caught.value.__notes__)


def test_failure_before_factory_completion_leaves_factory_rollback_in_charge(monkeypatch):
    import svx.inheritance as inheritance
    closed = []

    class Failed(SVMirror):
        __svx_guard_descendant_initializers__ = True

        def __init__(self):
            super().__init__()
            self._svx_bind_remote_object(91)
            raise ValueError('factory stage failed')

    monkeypatch.setattr(inheritance, 'close_instance', closed.append)
    with pytest.raises(ValueError, match='factory stage failed'):
        Failed()
    assert closed == []


def test_baseexception_also_restores_depth_and_retires_new_target(guarded):
    Base, _, captured, events = guarded

    class Interrupted(Base):
        def __init__(self, seed=4):
            super().__init__(seed)
            raise KeyboardInterrupt('initializer interrupted')

    with pytest.raises(KeyboardInterrupt, match='initializer interrupted'):
        Interrupted(91)
    owner = captured[0]
    assert events == [('storage', owner), ('target', owner)]
    assert owner._svx_initializer_depth == 0
