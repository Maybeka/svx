import io
import json

import pytest

from svx.cli import main, _artifact_change_diagnostic
from tests.python.test_python_source_inputs import generation_args


def test_python_only_stale_diagnostic_identifies_file_without_writes(tmp_path):
    source = tmp_path / 'source.py'
    source.write_text('raise RuntimeError("this input must not execute")\n')
    args = generation_args(tmp_path, source)
    main(args, out=io.StringIO())
    source.write_text(source.read_text() + '# body edit\n')
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in tmp_path.rglob('*') if path.is_file()}
    with pytest.raises(SystemExit) as caught:
        main(args + ['--check'], out=io.StringIO())
    message = str(caught.value)
    assert 'python_sources: changed "source.py"' in message
    assert 'Generated bridge files match; only recorded Python inputs changed.' in message
    assert 'Rerun discovery first if declarations changed.' in message
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in tmp_path.rglob('*') if path.is_file()} == before


def description(inputs, **extra):
    return json.dumps({'generation_inputs': inputs, **extra})


@pytest.mark.parametrize('key', ['sv_dependencies', 'manifest'])
def test_non_python_input_does_not_claim_input_record_only_refresh(key):
    old, new = {'path': 'source.sv', 'sha256': 'old'}, {'path': 'source.sv', 'sha256': 'new'}
    if key != 'manifest':
        old, new = [old], [new]
    result = _artifact_change_diagnostic(description({key: old}), description({key: new}), bridge_mismatches=False)
    assert f'{key}: changed "source.sv"' in result
    assert 'rebuild affected source inputs' in result
    assert 'only recorded Python inputs changed' not in result


@pytest.mark.parametrize('bridge_mismatches,metadata_changed', [(True, False), (False, True)])
def test_bridge_or_metadata_change_does_not_get_python_only_hint(bridge_mismatches, metadata_changed):
    old = description({'python_sources': [{'path': 'source.py', 'sha256': 'old'}]}, version=1)
    new = description({'python_sources': [{'path': 'source.py', 'sha256': 'new'}]}, version=2 if metadata_changed else 1)
    assert 'only recorded Python inputs changed' not in _artifact_change_diagnostic(
        old, new, bridge_mismatches=bridge_mismatches)


def test_changed_input_set_and_parse_configuration_are_explicit():
    old = description({'python_sources': [{'path': 'old.py', 'sha256': 'old'}], 'sv_include_dirs': ['a']})
    new = description({'python_sources': [{'path': 'new.py', 'sha256': 'new'}], 'sv_include_dirs': ['b']})
    result = _artifact_change_diagnostic(old, new, bridge_mismatches=False)
    assert 'python_sources: added "new.py"' in result
    assert 'python_sources: removed "old.py"' in result
    assert 'sv_include_dirs: changed' in result


@pytest.mark.parametrize('previous', [None, '{', '[]', '{}'])
def test_missing_or_malformed_metadata_has_no_python_only_claim(previous):
    result = _artifact_change_diagnostic(previous, description({'python_sources': []}), bridge_mismatches=False)
    assert 'regenerate' in result
    assert 'only recorded Python inputs changed' not in result
