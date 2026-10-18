"""Explicit bootstrap import used by generated UVMX launch flows."""

from __future__ import annotations

import importlib
import svx
from svx.callbacks import CallbackAdapter

from .declarations import UvmTestDeclaration, declared_tests, PHASE_CALLBACKS
from .registration import UvmxRegistration


REGISTRATION_CHANNEL = 'uvmx.bootstrap.registration'
PHASE_ADAPTER = CallbackAdapter('py://uvmx/runtime/Test', PHASE_CALLBACKS)


@svx.export(name='uvmx.bootstrap.publish_tests')
def _publish_tests():
    channel = svx.channel(REGISTRATION_CHANNEL)
    for declaration in declared_tests():
        metadata = UvmxRegistration()
        metadata.canonical_id.value = declaration.canonical_id
        metadata.factory_name.value = declaration.factory_name
        metadata.sv_base.value = declaration.sv_base
        channel.put(metadata)
    end = UvmxRegistration()
    end.finished.value = 1
    channel.put(end)


def load_declarations(module_name: str) -> tuple[UvmTestDeclaration, ...]:
    """Import an opt-in test module and return only its declarations."""

    importlib.import_module(module_name)
    declarations = declared_tests(module_name)
    if not declarations:
        raise RuntimeError(f"UVMX module {module_name!r} did not declare any @uvm_test classes")
    return declarations
