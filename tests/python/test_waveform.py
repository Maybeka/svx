from pathlib import Path
import subprocess
import sys
import tomllib

import pytest
import svx
from svx import waveform
from svx.callback_context import blocking_operations_disallowed


@pytest.fixture
def native(monkeypatch):
    calls = []
    monkeypatch.setattr(waveform._native, 'waveform_available', lambda: True)
    monkeypatch.setattr(waveform._native, 'waveform_begin', lambda *args: calls.append(('begin', *args)))
    monkeypatch.setattr(waveform._native, 'waveform_command', lambda *args: calls.append(('command', *args)))
    monkeypatch.setattr(waveform._native, 'waveform_state', lambda: 'paused')
    return calls


def test_import_does_not_require_native_or_simulator():
    result = subprocess.run([sys.executable, '-c',
        'import sys, svx; assert "_svx_native" not in sys.modules; '
        'assert svx.waveform.capabilities() == frozenset()'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_optional_wrapper_is_in_wheel_build_inputs():
    root = Path(__file__).resolve().parents[2]
    data = tomllib.loads((root / 'pyproject.toml').read_text())
    assert 'sv/svx_waveform.sv' in data['tool']['setuptools']['data-files']['share/svx/sv']
    assert '`include "sv/svx_waveform.sv"' in (root / 'sv/svx_pkg.sv').read_text()


def test_begin_preserves_multiple_scopes_and_pathlike(native):
    waveform.begin(Path('next.fsdb'), scopes=(scope for scope in [('tb.left', 0), ('tb.right', 2)]))
    assert native == [('begin', 'next.fsdb', (('tb.left', 0), ('tb.right', 2)))]
    assert waveform.state() is waveform.State.PAUSED
    assert 'finish_restart' in waveform.capabilities()


def test_control_operation_mapping(native):
    waveform.pause()
    waveform.resume()
    waveform.flush()
    waveform.switch_file('next.fsdb')
    waveform.add_scope('tb.other', 2)
    waveform.finish()
    assert native == [('command', 3, '', 0), ('command', 4, '', 0),
                      ('command', 5, '', 0), ('command', 6, 'next.fsdb', 0),
                      ('command', 2, 'tb.other', 2), ('command', 7, '', 0)]


@pytest.mark.parametrize('scopes,exception', [
    ([], ValueError), ([('', 0)], ValueError), ([('tb\0bad', 0)], ValueError),
    ([('tb', -1)], ValueError), ([('tb', 2**31)], ValueError),
    ([('tb', True)], TypeError), ([('tb', 1.5)], TypeError),
    ([('tb.good', 0), ('tb.bad', -1)], ValueError),
])
def test_bad_scope_list_rejected_before_native_changes(native, scopes, exception):
    with pytest.raises(exception):
        waveform.begin('next.fsdb', scopes=scopes)
    assert not native


@pytest.mark.parametrize('path', ['', 'bad\0file', b'bytes.fsdb'])
def test_bad_filename(native, path):
    with pytest.raises(ValueError):
        waveform.begin(path, scopes=[('tb', 0)])
    assert not native


def test_no_backend_has_explicit_error(monkeypatch):
    monkeypatch.setattr(waveform._native, 'waveform_available', lambda: False)
    assert not waveform.capabilities()
    with pytest.raises(svx.SVXWaveformError, match='no compatible waveform bridge'):
        waveform.begin('next.fsdb', scopes=[('tb', 0)])


@pytest.mark.parametrize('operation', [lambda: waveform.begin('next.fsdb', scopes=[('tb', 0)]),
    waveform.pause, waveform.resume, waveform.flush, waveform.finish,
    lambda: waveform.add_scope('tb'), lambda: waveform.switch_file('next.fsdb')])
def test_function_callback_cannot_enter_waveform_task(native, operation):
    with blocking_operations_disallowed('executing an SV function callback'):
        with pytest.raises(svx.SVXContextError, match='svx.waveform'):
            operation()
    assert not native
