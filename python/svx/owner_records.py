"""Shared declarations for transport records emitted outside SV packages."""

from contextvars import ContextVar
from functools import wraps
from dataclasses import replace
import json

from .value_exports import native_value_name


_local_call_records = ContextVar('svx_local_call_records', default=False)


def emit_owner_initializer(key, *, owner_root=None, owner_path=None):
    """Register one lexical callback without invoking user constructors early."""
    conditions = ['1']
    if owner_root is not None:
        parts = owner_path.split('.')
        start = len(owner_root.split('.'))
        scopes = ['.'.join(parts[:length]) for length in range(start, len(parts)+1)]
        scopes.append(key)
        conditions = ['scope == ' + json.dumps(scope) for scope in scopes]
    return [
        'class SVXOwnerInitializer implements svx_owner_initializer;',
        '  function new(string scope);',
        '    if (' + ' || '.join(conditions) + ')',
        '      svx_inheritance_registry::register_owner_initializer(' + json.dumps(key) + ', this);',
        '  endfunction',
        '  virtual function void svx_initialize_owner();',
        '    initialize();',
        '  endfunction',
        'endclass',
        'SVXOwnerInitializer svx_owner_bootstrap = new($sformatf("%m"));',
    ]


def with_local_call_records(function):
    """Keep collection aliases in the native scope that owns their records."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = _local_call_records.set(True)
        try:
            return function(*args, **kwargs)
        finally:
            _local_call_records.reset(token)
    return wrapped


def bind_owner_types(source, native_references):
    """Change native spellings only; public SvTypes wire contracts stay intact."""
    def binding(value):
        return replace(value, sv=native_references.get(value.sv, value.sv)) if value is not None else None
    def parameters(values):
        return tuple(replace(value, type_binding=binding(value.type_binding)) for value in values)
    return replace(source,
        fields=tuple(replace(value, type_binding=binding(value.type_binding)) for value in source.fields),
        constructor=replace(source.constructor, parameters=parameters(source.constructor.parameters)) if source.constructor else None,
        methods=tuple(replace(value, parameters=parameters(value.parameters), return_type=binding(value.return_type))
                      for value in source.methods),
        base_lineage=tuple(bind_owner_types(value, native_references) for value in source.base_lineage))


def emit_owner_records(manifest, source_scope, *, native_references=None):
    """Render actual nominal dependencies in the caller's codegen value scope."""
    import svtypes
    from .inheritance import (
        _codec_from_spec, _transport_owners, _manifest_sv_collection_typedefs,
        _manifest_sv_record_types,
    )

    bindings = []
    for owner in _transport_owners(manifest):
        bindings.extend(field.type_binding for field in owner.fields)
        bindings.extend(parameter.type_binding for parameter in (owner.constructor.parameters if owner.constructor else ()))
        for method in owner.methods:
            bindings.extend(parameter.type_binding for parameter in method.parameters)
            if method.return_type is not None:
                bindings.append(method.return_type)
    needed = set()

    def named_dependencies(schema):
        if isinstance(schema, dict):
            if isinstance(schema.get('type_name'), str):
                needed.add(schema['type_name'])
            for item in schema.values():
                named_dependencies(item)
        elif isinstance(schema, list):
            for item in schema:
                named_dependencies(item)

    for binding in bindings:
        named_dependencies(svtypes.schema_descriptor(_codec_from_spec(binding.runtime_spec())).to_dict())
    definitions = []
    for value in manifest.value_types:
        if value.source_scope is not None and value.source_scope != source_scope:
            continue
        data = value.as_dict()
        if (data['schema']['type_name'] in needed
                and data['schema']['type_name'] == value.module + '.' + value.qualname):
            definitions.append((value, data))
    lines = [f'import {package}::*;' for package in sorted({value.symbol.split('::')[0]
             for value, _ in definitions if value.source_scope is None})]
    for value, data in definitions:
        if data['schema']['kind'] == 'enum':
            reference = (native_references or {}).get(value.symbol, value.symbol)
            lines.append(f'typedef {reference} {native_value_name(value.symbol, value.source_scope)};')
        elif data['schema']['kind'] == 'struct':
            model = svtypes.type_spec_from_identity(data['svtypes'], location=value.symbol)
            lines.append(model.to_sv_obj(0))
    lines.extend(_manifest_sv_collection_typedefs(manifest))
    lines.extend(record.to_sv_obj(0) for record in _manifest_sv_record_types(manifest))
    return lines
