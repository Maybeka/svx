import traceback

import pytest

from svx import _native
from svx.errors import SVXCancellationError, SVXRemoteError
from svx.inheritance import call_sv, call_sv_static, dispatch_python_call, register_contract
from svx._inheritance_diagnostics import _call_path


def test_nested_boundary_preserves_original_error_traceback_and_complete_path(monkeypatch):
    method_id = 'py://diagnostics/Receiver#check'
    original = ValueError('original user failure')

    class Receiver:
        def check(self):
            raise original

    register_contract({method_id: {'parameters': (), 'request': (), 'response': (), 'timing': 'function'}})
    monkeypatch.setattr(_native, 'inheritance_get', lambda _: Receiver())
    monkeypatch.setattr(_native, 'inheritance_call_sv',
                        lambda object_id, *_args, **_kwargs: dispatch_python_call(object_id, method_id, b'', True))
    with pytest.raises(ValueError) as caught:
        call_sv(41, 'sv://diagnostics/Base#check')
    assert caught.value is original
    notes = [note for note in original.__notes__ if note.startswith('SVX call path: ')]
    assert len(notes) == 1
    assert 'Python -> SV object=41 method_id=sv://diagnostics/Base#check' in notes[0]
    assert 'SV -> Python object=41 method_id=py://diagnostics/Receiver#check' in notes[0]
    frames = traceback.extract_tb(original.__traceback__)
    assert frames[-1].name == 'check'
    assert _call_path.get() == ()


def test_remote_error_keeps_structured_identity_cause_and_path(monkeypatch):
    original = RuntimeError('SVX1|dispatch_failed|72|sv://diagnostics/Base#run|original SV error')
    def fail(*_args, **_kwargs):
        raise original
    monkeypatch.setattr(_native, 'inheritance_call_sv', fail)
    with pytest.raises(SVXRemoteError) as caught:
        call_sv(object_id=72, method_id='sv://diagnostics/Base#run')
    assert caught.value.__cause__ is original
    assert caught.value.code == 'dispatch_failed'
    assert caught.value.object_id == 72
    assert caught.value.remote_message == 'original SV error'
    assert 'Python -> SV object=72' in caught.value.__notes__[0]
    assert _call_path.get() == ()


def test_cancellation_is_not_reclassified_or_annotated(monkeypatch):
    original = SVXCancellationError('stopped')
    def interrupted(*_args, **_kwargs):
        raise original
    monkeypatch.setattr(_native, 'inheritance_call_sv', interrupted)
    with pytest.raises(SVXCancellationError) as caught:
        call_sv(41, 'sv://diagnostics/Base#run')
    assert caught.value is original and not getattr(original, '__notes__', ())
    assert _call_path.get() == ()


def test_static_boundary_reports_method_without_allocating_receiver(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError('static failure')
    monkeypatch.setattr(_native, 'inheritance_call_sv_static', fail)
    with pytest.raises(SVXRemoteError) as caught:
        call_sv_static('sv://diagnostics/Base', 'sv://diagnostics/Base#scale')
    assert 'Python -> SV static object=0 method_id=sv://diagnostics/Base#scale' in caught.value.__notes__[0]
    assert _call_path.get() == ()


def test_bound_field_transport_reports_field_identity_and_preserves_cause(monkeypatch):
    from svx.field_storage import _NativeFieldTransport
    original = RuntimeError('field failure')
    def fail(*_args, **_kwargs):
        raise original
    monkeypatch.setattr(_native, 'inheritance_call_sv', fail)
    with pytest.raises(RuntimeError) as caught:
        _NativeFieldTransport().read_field(72, 'sv://diagnostics/Base.matrix', '{}', '[]')
    assert caught.value is original
    assert 'Python -> SV field read object=72 field_id=sv://diagnostics/Base.matrix' in original.__notes__[0]
    assert _call_path.get() == ()
