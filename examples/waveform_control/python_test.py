"""Record two independent waveform selections using the optional backend."""

import os
from pathlib import Path

import svx


@svx.export(name='waveform_control.run')
def run():
    output = Path(os.environ.get('SVX_WAVEFORM_OUTPUT', 'waveforms'))
    output.mkdir(parents=True, exist_ok=True)
    wave = svx.waveform
    wave.begin(output / 'first.fsdb', scopes=[('tb.dut', 1)])
    svx.delay(5, 'ns')
    wave.pause()
    svx.delay(5, 'ns')
    wave.resume()
    svx.delay(5, 'ns')
    wave.switch_file(output / 'continued.fsdb')
    wave.add_scope('tb.dut.child', 0)
    svx.delay(5, 'ns')
    wave.flush()
    wave.finish()
    svx.delay(5, 'ns')
    wave.begin(output / 'second.fsdb',
               scopes=[('tb.dut.child', 0), ('tb.other', 0)])
    svx.delay(5, 'ns')
    wave.finish()
    svx.display('WAVEFORM_CONTROL_PASS')
