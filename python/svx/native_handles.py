"""Shared typed endpoints for native class and VIF values in source owners."""

from contextvars import ContextVar
from dataclasses import replace
from functools import wraps
from .value_exports import with_value_types

_targets = ContextVar('svx_native_handle_targets', default=frozenset())
_aliases = ContextVar('svx_native_handle_aliases', default=None)
_record_targets = ContextVar('svx_shared_handle_record_targets', default=frozenset())
_nominal_types = ContextVar('svx_native_handle_nominal_types', default=None)


def uses_generic_handle(binding):
    return binding.target_type_name in _targets.get()


def uses_bound_call_records(binding):
    return binding.target_type_name in (_nominal_types.get() or {})


def generic_handle_reference(binding, stem):
    if uses_generic_handle(binding):
        alias = (_aliases.get() or {}).get((stem, binding.sv_type))
        if alias is not None:
            return alias
        return generic_handle_specialization(binding, stem)
    return stem


def generic_handle_specialization(binding, stem):
    types = (_nominal_types.get() or {}).get(binding.target_type_name, ())
    arguments = ', '.join((binding.sv_type, *(value.native_reference for value in types)))
    return f'svx_scoped_handles_pkg::{stem}#({arguments})'


def with_native_handle_adapters(function):
    @wraps(function)
    def wrapped(manifest, *args, **kwargs):
        from .inheritance import _all_manifest_classes, _manifest_handle_bindings

        if _targets.get() or not any(owner.source_scope is not None for owner in _all_manifest_classes(manifest)):
            return function(manifest, *args, **kwargs)
        from .value_exports import value_modules
        with value_modules(manifest.value_types, codegen=True):
            nominal = {binding.target_type_name: types for binding in _manifest_handle_bindings(manifest)
                       if binding.collection_binding is None
                       and (types := _nominal_operation_types(binding, manifest.value_types))}
            targets = frozenset(binding.target_type_name for binding in _manifest_handle_bindings(manifest)
                                if binding.collection_binding is None
                                and (binding.kind == 'sv_class' or _portable_operations(binding)
                                     or binding.target_type_name in nominal))
            records = frozenset(source.canonical_id for source in manifest.classes
                if source.source_scope is not None and _portable_handle_records(
                    replace(manifest, classes=(source,), callables=())))
        token = _targets.set(targets)
        alias_token = _aliases.set({})
        record_token = _record_targets.set(records)
        nominal_token = _nominal_types.set(nominal)
        try:
            return function(manifest, *args, **kwargs)
        finally:
            _targets.reset(token)
            _aliases.reset(alias_token)
            _record_targets.reset(record_token)
            _nominal_types.reset(nominal_token)
    return wrapped


def register_native_handle_alias(binding, reference):
    from .inheritance import _handle_adapter_stem
    _aliases.get()[(_handle_adapter_stem(binding), binding.sv_type)] = reference


def _portable_handle_records(manifest):
    import svtypes
    from .inheritance import _codec_from_spec, _manifest_handle_bindings, _transport_owners

    if not _manifest_handle_bindings(manifest):
        return False
    for owner in _transport_owners(manifest):
        bindings = [field.type_binding for field in owner.fields]
        bindings.extend(parameter.type_binding for parameter in (owner.constructor.parameters if owner.constructor else ()))
        for method in owner.methods:
            bindings.extend(parameter.type_binding for parameter in method.parameters)
            if method.return_type is not None:
                bindings.append(method.return_type)
        if any(not _portable_schema(svtypes.schema_descriptor(_codec_from_spec(binding.runtime_spec())).schema)
               for binding in bindings):
            return False
    if any(not _portable_operations(binding) for binding in _manifest_handle_bindings(manifest)):
        return False
    return True


def _portable_schema(schema):
    kind = schema['kind']
    if kind in {'bits', 'real', 'string', 'remote_ref'}:
        return True
    if kind in {'array', 'dyn_array', 'queue'}:
        return _portable_schema(schema['element'])
    if kind == 'assoc_array':
        return _portable_schema(schema['key']) and _portable_schema(schema['value'])
    return False


def _portable_operations(binding):
    import svtypes
    from .inheritance import _codec_from_spec
    if any(operation.method.return_handle is not None or
           any(parameter.handle is not None for parameter in operation.method.parameters)
           for operation in binding.operations):
        return False
    types = [parameter.type_binding for operation in binding.operations
             for parameter in operation.method.parameters]
    types.extend(operation.method.return_type for operation in binding.operations
                 if operation.method.return_type is not None)
    for value in types:
        codec = _codec_from_spec(value.runtime_spec())
        if not _portable_schema(svtypes.schema_descriptor(codec).schema):
            return False
    return True


def _nominal_operation_types(binding, values):
    """Select actual named value dependencies, never infer native type by value."""
    import svtypes
    from .inheritance import _codec_from_spec
    if binding.kind != 'virtual_interface' or any(operation.method.return_handle is not None or
            any(parameter.handle is not None for parameter in operation.method.parameters)
            for operation in binding.operations):
        return ()
    needed = set()
    def visit(schema):
        if schema['kind'] in {'enum', 'struct'}:
            needed.add(schema['type_name'])
        if schema['kind'] == 'struct':
            return all(visit(field['type']) for field in schema['fields'])
        if schema['kind'] == 'enum':
            return True
        if schema['kind'] in {'array', 'dyn_array', 'queue'}:
            return visit(schema['element'])
        if schema['kind'] == 'assoc_array':
            return visit(schema['key']) and visit(schema['value'])
        return _portable_schema(schema)
    types = [parameter.type_binding for operation in binding.operations for parameter in operation.method.parameters]
    types.extend(operation.method.return_type for operation in binding.operations if operation.method.return_type is not None)
    if not all(visit(svtypes.schema_descriptor(_codec_from_spec(value.runtime_spec())).schema) for value in types):
        return ()
    selected = tuple(value for value in values if value.as_dict()['schema']['type_name'] in needed
                     and value.as_dict()['schema']['kind'] in {'enum', 'struct'}
                     and value.as_dict()['schema']['type_name'] == value.module + '.' + value.qualname)
    if (not needed or {value.as_dict()['schema']['type_name'] for value in selected} != needed
            or any(value.source_scope is not None for value in selected)):
        return ()
    return selected


def _portable_vif_manifest(manifest):
    """Use structural temporaries for aliases, without changing wire identities."""
    import svtypes
    from .inheritance import _codec_from_spec

    def value(binding):
        if binding is None or binding.sv.strip() in {
                'bit', 'logic', 'reg', 'byte', 'shortint', 'int', 'longint',
                'integer', 'time', 'shortreal', 'real', 'string'}:
            return binding
        return replace(binding, sv=svtypes.sv_type_expression(_codec_from_spec(binding.runtime_spec())))
    def handle(binding):
        if binding is None or binding.kind != 'virtual_interface' or not uses_generic_handle(binding):
            return binding
        return replace(binding, operations=tuple(replace(operation, method=replace(operation.method,
            parameters=tuple(replace(parameter, type_binding=value(parameter.type_binding))
                             for parameter in operation.method.parameters),
            return_type=value(operation.method.return_type))) for operation in binding.operations))
    def parameters(items):
        return tuple(replace(item, handle=handle(item.handle)) for item in items)
    def owner(source):
        return replace(source,
            fields=tuple(replace(field, handle=handle(field.handle)) for field in source.fields),
            constructor=replace(source.constructor, parameters=parameters(source.constructor.parameters)) if source.constructor else None,
            methods=tuple(replace(method, parameters=parameters(method.parameters), return_handle=handle(method.return_handle))
                          for method in source.methods),
            base_lineage=tuple(owner(base) for base in source.base_lineage))
    return replace(manifest, classes=tuple(owner(source) for source in manifest.classes),
        callables=tuple(replace(item, method=replace(item.method, parameters=parameters(item.method.parameters),
                                                   return_handle=handle(item.method.return_handle)))
                        for item in manifest.callables))


def uses_shared_handle_records(manifest):
    return bool(manifest.classes) and all(source.canonical_id in _record_targets.get() for source in manifest.classes)


def _emit_nominal_call_records(manifest, bindings):
    from .inheritance import (ForeignClass, _handle_adapter_stem,
                              _manifest_sv_record_types, _sv_collection_typedef)
    from .owner_records import emit_owner_records
    from .value_exports import native_value_name
    lines, scopes = [], {}
    for binding in bindings:
        if binding.collection_binding is not None:
            continue
        values = (_nominal_types.get() or {}).get(binding.target_type_name)
        if values is None:
            continue
        parameters = tuple('SVXNativeValueType_' + str(index) for index in range(len(values)))
        references = {value.symbol: parameter for value, parameter in zip(values, parameters)}
        source = ForeignClass('svx-internal://vif-records/' + binding.target_type_name,
                              'sv', 'SVXVifRecords', tuple(item.method for item in binding.operations), None)
        local = replace(manifest, classes=(source,), callables=(), value_types=values)
        packers = {}
        declarations = emit_owner_records(local, None, native_references=references,
            inline=True, local_enum_packers=packers, native_struct_aliases=True)
        for original, replacement in packers.items():
            declarations = [line.replace(original, replacement) for line in declarations]
        aliases = [native_value_name(value.symbol) + ('_t' if value.as_dict()['schema']['kind'] == 'struct' else '')
                   for value in values]
        for method in source.methods:
            types = [parameter.type_binding for parameter in method.parameters]
            if method.return_type is not None:
                types.append(method.return_type)
            for value in types:
                collection = _sv_collection_typedef(value)
                if collection is not None:
                    aliases.append(collection[0])
        aliases.extend(record.__name__ for record in _manifest_sv_record_types(local))
        name = _handle_adapter_stem(binding) + 'Records'
        lines.extend(['class ' + name + ' #(' + ', '.join('type ' + item for item in parameters) + ');',
                      *declarations, 'endclass : ' + name])
        scopes[binding.target_type_name] = {'name': name, 'parameters': parameters,
                                            'aliases': tuple(dict.fromkeys(aliases))}
    return lines, scopes


@with_value_types(codegen=True)
def emit_native_handle_adapters(manifest):
    from .inheritance import _emit_sv_external_handle_adapters, _manifest_handle_bindings, _generated_sv_header

    manifest = _portable_vif_manifest(manifest)
    bindings = tuple(replace(binding, sv_type='SVXNativeHandleType')
                     for binding in _manifest_handle_bindings(manifest) if uses_generic_handle(binding))
    if not bindings:
        return ''
    token = _targets.set(frozenset())
    try:
        from .owner_records import with_local_call_records
        declarations, scopes = with_local_call_records(_emit_nominal_call_records)(manifest, bindings)
        lines = with_local_call_records(_emit_sv_external_handle_adapters)(manifest,
            package_name='svx_scoped_handles_pkg', bindings=bindings,
            native_type_parameter='SVXNativeHandleType', native_call_records=scopes)
        offset = lines.index('  import svtypes_pkg::*;') + 1
        lines[offset:offset] = declarations
        classes = tuple(source for source in manifest.classes if source.canonical_id in _record_targets.get())
        shared = replace(manifest, classes=classes, callables=())
        covered = {operation.method.canonical_id for binding in _manifest_handle_bindings(shared)
                   for operation in binding.operations}
        missing = {operation.method.canonical_id: operation.method for binding in bindings
                   if binding.target_type_name not in scopes
                   for operation in binding.operations if operation.method.canonical_id not in covered}
        if missing:
            from .inheritance import ForeignClass
            # VIF dispatch records must not depend on whether the consuming API
            # class also has native-owner enum or struct fields.
            classes += (ForeignClass('svx-internal://vif-records', 'sv', 'SVXVifRecords',
                                     tuple(missing[key] for key in sorted(missing)), None),)
        if classes:
            from .owner_records import emit_owner_records, with_local_call_records
            records = with_local_call_records(emit_owner_records)(
                replace(manifest, classes=classes, callables=()), None, inline=True)
            offset = lines.index('  import svtypes_pkg::*;') + 1
            lines[offset:offset] = records
        return '\n'.join([*_generated_sv_header(manifest), *lines])
    finally:
        _targets.reset(token)
