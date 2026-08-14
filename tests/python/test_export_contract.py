from __future__ import annotations

import pytest

import svx
from svx import _registry


@pytest.fixture(autouse=True)
def empty_registry():
    _registry.clear()
    yield
    _registry.clear()


def test_export_rejects_invalid_name_and_nonzero_argument_signature():
    with pytest.raises(svx.SVXExportError, match="non-empty"):
        svx.export(name="")(lambda: None)

    with pytest.raises(svx.SVXExportError, match="must accept no arguments"):
        svx.export(lambda value: value)


def test_export_rejects_duplicate_identity():
    svx.export(name="project.run")(lambda: None)
    with pytest.raises(svx.SVXExportError, match="already registered"):
        svx.export(name="project.run")(lambda: None)
