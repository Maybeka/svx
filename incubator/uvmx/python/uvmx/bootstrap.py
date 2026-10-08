"""Explicit bootstrap import used by generated UVMX launch flows."""

from __future__ import annotations

import importlib

from .declarations import UvmTestDeclaration, declared_tests


def load_declarations(module_name: str) -> tuple[UvmTestDeclaration, ...]:
    """Import an opt-in test module and return only its declarations."""

    importlib.import_module(module_name)
    declarations = declared_tests(module_name)
    if not declarations:
        raise RuntimeError(f"UVMX module {module_name!r} did not declare any @uvm_test classes")
    return declarations
