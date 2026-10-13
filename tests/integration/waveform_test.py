import os
from pathlib import Path
import svx


def rejected(call, message):
    try:
        call()
    except svx.SVXWaveformError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError('invalid waveform operation unexpectedly succeeded')


@svx.export(name='waveform.check')
def check():
    wave = svx.waveform
    output = Path(os.environ['SVX_WAVEFORM_OUTPUT'])
    output.mkdir(parents=True, exist_ok=True)
    assert wave.state() is wave.State.IDLE
    if os.environ.get('SVX_WAVEFORM_EXPECT_DISABLED') == '1':
        assert not wave.capabilities()
        rejected(lambda: wave.begin(output / 'disabled.fsdb', scopes=[('tb.dut', 0)]),
                 'no compatible waveform bridge')
        assert not (output / 'disabled.fsdb').exists()
        svx.display('WAVEFORM_DISABLED_PASS')
        return
    assert wave.capabilities() == frozenset({'string_scopes', 'dynamic_depth',
        'pause_resume', 'switch_file', 'add_scope', 'finish_restart'})
    for call in [wave.pause, wave.resume, wave.flush,
                 lambda: wave.switch_file(output / 'early.fsdb')]:
        rejected(call, 'active recording')
    wave.finish()
    rejected(lambda: wave.begin(output / 'bad.fsdb',
        scopes=[('tb.dut', 1), ('tb.missing', 0)]), 'scope is missing')
    assert not (output / 'bad.fsdb').exists()
    rejected(lambda: wave.begin(output / 'signal.fsdb', scopes=[('tb.dut.clk', 0)]),
             'module scope')
    wave.begin(output / 'checked.fsdb', scopes=[('tb.dut', 1)])
    rejected(lambda: wave.begin(output / 'busy.fsdb', scopes=[('tb.other', 0)]),
             'requires finish')
    assert not (output / 'busy.fsdb').exists()
    rejected(lambda: wave.add_scope('tb.missing'), 'scope is missing')
    svx.delay(2, 'ns')
    wave.pause()
    wave.pause()
    assert wave.state() is wave.State.PAUSED
    rejected(lambda: wave.switch_file(output / 'checked.fsdb'), 'already exists or was used')
    wave.switch_file(output / 'paused.fsdb')
    assert wave.state() is wave.State.PAUSED
    wave.add_scope('tb.other', 0)
    svx.delay(2, 'ns')
    wave.resume()
    wave.resume()
    assert wave.state() is wave.State.RECORDING
    svx.delay(2, 'ns')
    wave.finish()
    wave.finish()
    rejected(lambda: wave.begin(output / 'checked.fsdb', scopes=[('tb.other', 0)]),
             'already exists or was used')
    assert wave.state() is wave.State.IDLE
    svx.display('WAVEFORM_VALIDATION_PASS')
