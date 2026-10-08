import importlib
import os
import py_compile
import sys

import pytest

from svx.runtime import _native_load


def test_runtime_load_reads_current_source_and_dependencies(tmp_path, monkeypatch):
    names = ('runtime_source_entry', 'runtime_source_helper')
    sources = ('from runtime_source_helper import VALUE\n', 'VALUE = 10\n')
    for name, source in zip(names, sources):
        path = tmp_path / (name + '.py')
        path.write_text(source)
        os.utime(path, (1700000000, 1700000000))
        py_compile.compile(str(path), doraise=True)
    helper = tmp_path / (names[1] + '.py')
    helper.write_text('VALUE = 20\n')
    os.utime(helper, (1700000000, 1700000000))
    monkeypatch.syspath_prepend(str(tmp_path))
    before = list(sys.meta_path)
    try:
        module = _native_load(names[0])
        assert module.VALUE == 20
        assert _native_load(names[0]) is module
        assert sys.meta_path == before
    finally:
        for name in names:
            sys.modules.pop(name, None)


def test_runtime_load_restores_importers_after_failure(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / 'runtime_source_failure.py').write_text("raise RuntimeError('load failed')\n")
    before = list(sys.meta_path)
    with pytest.raises(RuntimeError, match='load failed'):
        _native_load('runtime_source_failure')
    assert sys.meta_path == before
    assert 'runtime_source_failure' not in sys.modules


def test_runtime_load_preserves_existing_custom_importer(monkeypatch):
    class ExistingImporter:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == 'runtime_custom_module':
                return importlib.util.spec_from_loader(fullname, self)

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.VALUE = 41

    monkeypatch.setattr(sys, 'meta_path', [ExistingImporter(), *sys.meta_path])
    try:
        assert _native_load('runtime_custom_module').VALUE == 41
    finally:
        sys.modules.pop('runtime_custom_module', None)
