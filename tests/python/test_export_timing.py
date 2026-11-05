import io
import json

import pytest

from svx.cli import main
from svx.export_timing import export_report, measured, phase


def test_phase_measurement_and_cleanup(monkeypatch):
    import svx.export_timing as timing
    ticks = iter([0, 1, 2, 4, 7, 10])
    monkeypatch.setattr(timing, 'perf_counter', lambda: next(ticks))
    out = io.StringIO()
    with export_report(True, out):
        with phase('Parent'):
            with phase('Child'):
                pass
    assert '  Parent: 6.000000 s (1 calls)' in out.getvalue()
    assert '    Child: 2.000000 s (1 calls)' in out.getvalue()
    assert '    Self / uninstrumented: 4.000000 s' in out.getvalue()
    assert 'Total: 10.000000 s' in out.getvalue()
    assert timing._report.get() is None


def test_disabled_measurement_never_reads_clock(monkeypatch):
    import svx.export_timing as timing
    def forbidden():
        pytest.fail('timing disabled')
    monkeypatch.setattr(timing, 'perf_counter', forbidden)
    @measured('Example')
    def example():
        with phase('Inner'):
            return 42
    out = io.StringIO()
    with export_report(False, out):
        assert example() == 42
    assert out.getvalue() == ''


def test_failure_reports_partial_time_and_preserves_exception():
    import svx.export_timing as timing
    out = io.StringIO()
    error = ValueError('original error')
    with pytest.raises(ValueError) as caught:
        with export_report(True, out), phase('Discovery'):
            raise error
    assert caught.value is error
    assert '(failed;' in out.getvalue()
    assert 'Discovery:' in out.getvalue()
    assert timing._report.get() is None


def test_export_report_does_not_change_artifacts_or_incremental_identity(tmp_path):
    pytest.importorskip('pyslang')
    source = tmp_path / 'classes.sv'
    source.write_text('package p; class Driver; int count; endclass endpackage', encoding='utf-8')
    root = tmp_path / 'generated'
    args = ['export', '--sv-source', str(source), '--package', 'p', '--out', str(root), '--incremental']
    def run(extra=()):
        out = io.StringIO()
        assert main(args + list(extra), out=out) == 0
        return out.getvalue()
    full = run(['--timings'])
    assert 'SVX export timings (completed;' in full
    for label in ('Compile configuration:', 'Discovery:', 'SV preprocessing, parsing and library search:',
                  'Semantic compilation (including reuse checks):', 'Generation:', 'Total:'):
        assert label in full
    cache = json.loads((root / '.svx-export-cache.json').read_text())
    assert 'SVX export timings' not in cache['summary']
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    assert 'SVX export timings' not in run(['--check'])
    reused = run(['--timings', '--check'])
    assert 'reused verified export' in reused
    assert 'Discovery:' not in reused
    assert 'Total:' in reused
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


def test_export_error_has_report_only_when_enabled(tmp_path):
    from svx.errors import SVXInheritanceError
    args = ['export', '--out', str(tmp_path), '--refresh-cache']
    for enabled in (False, True):
        out = io.StringIO()
        with pytest.raises(SVXInheritanceError, match='requires --incremental'):
            main(args + (['--timings'] if enabled else []), out=out)
        assert ('SVX export timings (failed;' in out.getvalue()) is enabled
