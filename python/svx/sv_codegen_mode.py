"""Generation policy for optional SystemVerilog type references."""
from contextlib import contextmanager
from contextvars import ContextVar

_use_type_reference = ContextVar('svx_use_type_reference', default=False)


def use_type_reference():
    return _use_type_reference.get()


def render_sv_object(value, indent):
    if use_type_reference():
        return value.to_sv_obj(indent, use_type_reference=True)
    return value.to_sv_obj(indent)


@contextmanager
def type_reference_mode(enabled):
    token = _use_type_reference.set(bool(enabled))
    try:
        yield
    finally:
        _use_type_reference.reset(token)
