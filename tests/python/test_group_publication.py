import os
from pathlib import Path

import pytest

import svx.inheritance as inheritance
from svx.errors import SVXInheritanceError


def snapshot(root):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino,
                   path.stat().st_mode)
            for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('point', ['staging', 'publish_before', 'publish_after'])
def test_group_failure_restores_original_files(tmp_path, monkeypatch, existing, point):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    if existing:
        a.write_text('old a')
        b.write_text('old b')
        a.chmod(0o640)
    before = snapshot(tmp_path)
    if point == 'staging':
        fsync = os.fsync
        calls = 0

        def fail_second_sync(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected staging failure')
            fsync(descriptor)

        monkeypatch.setattr(os, 'fsync', fail_second_sync)
    else:
        replace_file = Path.replace

        def fail_second_publication(source, destination):
            if source.name.endswith('.tmp') and Path(destination) == b:
                if point == 'publish_after':
                    replace_file(source, destination)
                raise OSError('injected publication failure')
            return replace_file(source, destination)

        monkeypatch.setattr(Path, 'replace', fail_second_publication)
    with pytest.raises(OSError, match='injected'):
        inheritance.write_text_atomic_group({a: 'new a', b: 'new b'})
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('after', [False, True])
def test_backup_move_failure_restores_originals(tmp_path, monkeypatch, after):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    a.write_text('old a')
    b.write_text('old b')
    before = snapshot(tmp_path)
    replace_file = Path.replace

    def fail_backup(source, destination):
        if source == b and Path(destination).name.endswith('.bak'):
            if after:
                replace_file(source, destination)
            raise OSError('injected backup move failure')
        return replace_file(source, destination)

    monkeypatch.setattr(Path, 'replace', fail_backup)
    with pytest.raises(OSError, match='backup move'):
        inheritance.write_text_atomic_group({a: 'new a', b: 'new b'})
    assert snapshot(tmp_path) == before


def test_group_success_preserves_matching_files(tmp_path):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    a.write_text('same a')
    before = snapshot(tmp_path)
    inheritance.write_text_atomic_group({a: 'same a', b: 'new b'})
    assert snapshot(tmp_path)[a] == before[a]
    complete = snapshot(tmp_path)
    inheritance.write_text_atomic_group({a: 'same a', b: 'new b'})
    assert snapshot(tmp_path) == complete


def test_group_rejects_symlink_output(tmp_path):
    source = tmp_path / 'source.json'
    source.write_text('source')
    target = tmp_path / 'target.json'
    target.symlink_to(source)
    before = snapshot(tmp_path)
    with pytest.raises(SVXInheritanceError, match='symlink output'):
        inheritance.write_text_atomic_group({target: 'new output'})
    assert snapshot(tmp_path) == before


def test_group_rejects_ancestor_conflict_before_staging(tmp_path):
    parent = tmp_path / 'output'
    with pytest.raises(SVXInheritanceError, match='paths conflict'):
        inheritance.write_text_atomic_group({parent: 'parent', parent / 'child.json': 'child'})
    assert not list(tmp_path.iterdir())


def test_failed_staging_removes_new_empty_directories(tmp_path, monkeypatch):
    parent = tmp_path / 'generated' / 'nested'

    def fail_sync(descriptor):
        raise OSError('injected staging failure')

    monkeypatch.setattr(os, 'fsync', fail_sync)
    with pytest.raises(OSError, match='staging failure'):
        inheritance.write_text_atomic_group({parent / 'output.json': 'new'})
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('independent_change', [False, True])
def test_failed_recovery_preserves_original_backup_and_independent_changes(
        tmp_path, monkeypatch, independent_change):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    a.write_text('old a')
    b.write_text('old b')
    replace_file = Path.replace

    def failed_restore(source, destination):
        if source.name.endswith('.tmp') and Path(destination) == b:
            replace_file(source, destination)
            if independent_change:
                b.write_text('independent change')
            raise OSError('injected publication failure')
        if source.name.endswith('.bak') and Path(destination) == b and not independent_change:
            raise OSError('injected recovery failure')
        return replace_file(source, destination)

    monkeypatch.setattr(Path, 'replace', failed_restore)
    with pytest.raises(SVXInheritanceError, match='recovery is incomplete'):
        inheritance.write_text_atomic_group({a: 'new a', b: 'new b'})
    assert a.read_text() == 'old a'
    assert b.read_text() == ('independent change' if independent_change else 'new b')
    backups = list(tmp_path.glob('*.bak'))
    assert len(backups) == 1
    assert backups[0].read_text() == 'old b'
    assert not list(tmp_path.glob('*.tmp'))
