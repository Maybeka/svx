from pathlib import Path, PurePosixPath
import sys

import pytest

from svx import runtime
from svx.errors import SVXError
from svx.generated_bootstrap import BOOTSTRAP_PATH, with_bootstrap


def test_bootstrap_runs_edited_core_without_inventory_or_hashes(tmp_path, monkeypatch):
    name = 'editable_generated_bootstrap_fixture'
    sources = with_bootstrap({PurePosixPath(name+'.py'): 'VALUE = 1\n'})
    for relative, text in sources.items():
        (tmp_path/relative).write_text(text, encoding='utf-8')
    (tmp_path/(name+'.py')).write_text('VALUE = 2\n', encoding='utf-8')
    monkeypatch.delenv('SVX_ARTIFACT_MANIFEST', raising=False)
    monkeypatch.setenv('SVX_BOOTSTRAP', str(tmp_path/BOOTSTRAP_PATH))
    monkeypatch.setattr(sys, 'path', list(sys.path))
    def forbidden(*args, **kwargs):
        pytest.fail('bootstrap must not read inventory or compute hashes')
    monkeypatch.setattr(runtime, '_load_artifact_manifest', forbidden)
    monkeypatch.setattr(runtime.hashlib, 'sha256', forbidden)
    try:
        runtime._load_configured_artifacts(None)
        assert sys.modules[name].VALUE == 2
    finally:
        sys.modules.pop(name, None)


def test_bootstrap_and_legacy_configuration_are_not_ambiguous(monkeypatch):
    monkeypatch.setenv('SVX_BOOTSTRAP', 'bootstrap.py')
    monkeypatch.setenv('SVX_ARTIFACT_MANIFEST', 'artifacts.json')
    with pytest.raises(SVXError, match='not both'):
        runtime._load_configured_artifacts(None)


def test_bootstrap_requires_explicit_entrypoint(tmp_path, monkeypatch):
    source = tmp_path/'bootstrap.py'
    source.write_text('VALUE = 1\n', encoding='utf-8')
    monkeypatch.setenv('SVX_BOOTSTRAP', str(source))
    monkeypatch.delenv('SVX_ARTIFACT_MANIFEST', raising=False)
    with pytest.raises(SVXError, match='initialize'):
        runtime._load_configured_artifacts(None)


def test_bootstrap_is_deterministic_and_does_not_import_itself():
    sources = {PurePosixPath('pkg/b.py'): '', PurePosixPath('pkg/__init__.py'): ''}
    assert with_bootstrap(sources) == with_bootstrap(dict(reversed(list(sources.items()))))
    text = with_bootstrap(sources)[BOOTSTRAP_PATH]
    assert "('pkg', 'pkg.b')" in text
    assert 'sha256' not in text
    with pytest.raises(ValueError, match='collides'):
        with_bootstrap(with_bootstrap(sources))
