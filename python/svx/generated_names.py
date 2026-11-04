"""Readable artifact-local names, independent of stable wire identities."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import re

_names = ContextVar('svx_generated_names', default=None)


@contextmanager
def sv_name_scope():
    """Allocate distinct helper names for one non-artifact SV operation."""
    if _names.get() is not None:
        yield
        return
    token = _names.set(({}, set()))
    try:
        yield
    finally:
        _names.reset(token)


def readable(text):
    text = re.sub(r'\b[A-Za-z_$][A-Za-z0-9_$]*::', '', text)
    name = re.sub(r'[^A-Za-z0-9_]+', '_', text).strip('_') or 'value'
    return 'value_' + name if name[0].isdigit() else name


def name_for(key, label):
    state = _names.get()
    if state is not None and key in state[0]:
        return state[0][key]
    if callable(label):
        label = label()
    base = '_svx__' + readable(label)[:72].rstrip('_')
    if state is None:
        return base
    assigned, occupied = state
    if key not in assigned:
        candidate = base
        index = 2
        while candidate in occupied:
            candidate = f'{base}_{index}'
            index += 1
        occupied.add(candidate)
        assigned[key] = candidate
    return assigned[key]


def schema_label(schema):
    kind = schema['kind']
    if kind in {'bits', 'logic'}:
        return ('int' if schema['signed'] else 'bits') + str(schema['width'])
    if kind == 'remote_ref':
        return 'handle'
    if kind in {'array', 'dyn_array', 'queue'}:
        container = {'array': 'fixed'+str(schema.get('size', '')),
                     'dyn_array': 'dynamic', 'queue': 'queue'}[kind]
        return container + '_' + schema_label(schema['element'])
    if kind == 'assoc_array':
        return 'by_' + schema_label(schema['key']) + '_' + schema_label(schema['value'])
    return kind


def with_sv_names(function):
    @wraps(function)
    def wrapped(manifest, *args, **kwargs):
        if _names.get() is not None:
            return function(manifest, *args, **kwargs)
        occupied = {item.name for item in manifest.classes}
        occupied.update(member.name for item in manifest.classes
                        for member in (*item.methods, *item.fields))
        token = _names.set(({}, occupied))
        try:
            return function(manifest, *args, **kwargs)
        finally:
            _names.reset(token)
    return wrapped
