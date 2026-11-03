"""Executable declaration loading is independent of artifact auditing."""
from types import SimpleNamespace

import pytest

from svx import runtime
from svx.errors import SVXError


def test_all_generated_modules_load_before_finalization(monkeypatch):
    events = []

    def load(name):
        events.append(('load', name))
        return SimpleNamespace(_svx_finalize_generated_types=lambda: events.append(('finish', name)))

    monkeypatch.setattr(runtime.importlib, 'import_module', load)
    runtime._load_generated_modules(['mirrors.base', 'mirrors.derived', 'mirrors.base'])
    assert events == [('load', 'mirrors.base'), ('load', 'mirrors.derived'),
                      ('finish', 'mirrors.base'), ('finish', 'mirrors.derived')]


@pytest.mark.parametrize('name', ['', '../source', 'pkg..module', 'pkg/module', 4, []])
def test_invalid_module_names_fail_before_import(monkeypatch, name):
    def forbidden(*args):
        pytest.fail('invalid registration must not import any modules')
    monkeypatch.setattr(runtime.importlib, 'import_module', forbidden)
    with pytest.raises(SVXError, match='qualified Python identifiers'):
        runtime._load_generated_modules(['valid.module', name])


def test_failed_import_does_not_finalize_partial_graph(monkeypatch):
    finished = []
    def load(name):
        if name == 'mirrors.broken':
            raise ImportError('missing declaration dependency')
        return SimpleNamespace(_svx_finalize_generated_types=lambda: finished.append(name))
    monkeypatch.setattr(runtime.importlib, 'import_module', load)
    with pytest.raises(ImportError, match='missing declaration dependency'):
        runtime._load_generated_modules(['mirrors.base', 'mirrors.broken'])
    assert finished == []
