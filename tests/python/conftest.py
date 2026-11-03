"""Helpers for tests consuming complete multi-file generated artifacts."""
import sys

import pytest


@pytest.fixture
def generated_artifacts(tmp_path, monkeypatch):
    snapshots = []

    def install(sources):
        root = tmp_path / ('generated-'+str(len(snapshots)))
        roots = {path.parts[0].removesuffix('.py') for path in sources}
        def owned(name):
            return name.split('.')[0] in roots
        previous = {name: module for name, module in sys.modules.items() if owned(name)}
        for name in previous:
            del sys.modules[name]
        snapshots.append((roots, previous))
        for relative, text in sources.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
        monkeypatch.syspath_prepend(str(root))
        return root

    yield install
    for roots, previous in reversed(snapshots):
        for name in list(sys.modules):
            if name.split('.')[0] in roots:
                del sys.modules[name]
        sys.modules.update(previous)
