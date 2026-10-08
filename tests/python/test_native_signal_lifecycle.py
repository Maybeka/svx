"""Native bookkeeping coverage, not a simulator/VPI qualification."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_native_signal_force_ledger_and_shutdown(tmp_path):
    compiler = shutil.which('c++')
    if compiler is None:
        pytest.skip('C++ compiler is unavailable')
    root = Path(__file__).resolve().parents[2]
    binary = tmp_path / 'signal_lifecycle'
    build = subprocess.run([
        compiler, '-std=c++20', '-I' + str(root / 'svx_runtime/include'),
        str(root / 'svx_runtime/src/signal.cpp'),
        str(root / 'tests/native/signal_lifecycle.cpp'), '-o', str(binary),
    ], capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stdout + build.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'NATIVE_SIGNAL_LEDGER_PASS'
    for name, count in [('released', 0), ('pending', 1), ('force_failed', 0),
                        ('overwrite_failed', 1), ('release_failed', 1)]:
        section = result.stderr.split('SIGNAL_CASE_BEGIN ' + name + '\n', 1)[1]
        section = section.split('SIGNAL_CASE_END ' + name + '\n', 1)[0]
        assert section.count('force still active at shutdown: tb.data') == count
