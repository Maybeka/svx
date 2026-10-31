"""Bind existing generated adapters to a concrete native instance owner."""

from dataclasses import replace

from .errors import SVXInheritanceError
from .owner_records import emit_owner_records, emit_owner_initializer, with_local_call_records, bind_owner_types
from .scoped_exports import _scope_component
from .source_scopes import instance_namespace_parts
from .value_exports import with_value_types


@with_value_types(codegen=True)
@with_local_call_records
def emit_instance_export_bridges(manifest, *, metadata=None, owner_insertions=None, local_owners=(), owner_roots=None):
    from .inheritance import (
        _all_manifest_classes, _effective_virtual_methods, _emit_sv_projection_class,
        _emit_sv_projection_factory, _emit_sv_static_gateway, _generated_sv_header,
        _manifest_handle_bindings, _sv_class_reference, _unbridged_sv_ancestors,
        projection_plans,
    )

    classes = tuple(source for source in manifest.classes
                    if source.source_scope is not None and source.source_scope['kind'] == 'instance')
    if not classes:
        return ''
    if any(plan.steps for plan in projection_plans(manifest)):
        raise SVXInheritanceError('instance-bound alternating lineage needs owner-aware projection placement; this layout remains unfinished')
    lines = [*_generated_sv_header(manifest), '']
    bindings = []
    registered_static = set()
    for source in classes:
        local = replace(manifest, classes=(source,), callables=())
        if any(owner.language != 'sv' for owner in _all_manifest_classes(local)):
            raise SVXInheritanceError('instance-bound class bridges currently require SV lineage')
        if _manifest_handle_bindings(local):
            raise SVXInheritanceError('instance-owned handle adapters need owner-bound type arguments; this layout remains unfinished')
        path = source.source_scope['path']
        container = source.source_scope.get('container', 'module')
        if container == 'program' and path not in local_owners:
            raise SVXInheritanceError('program class bridges require integrated source copies')
        if any(owner.source_scope is not None and owner.source_scope != source.source_scope
               for owner in source.base_lineage):
            raise SVXInheritanceError('instance ancestors from other native owners need explicit type binding; this layout remains unfinished')
        stem = '_'.join(map(_scope_component, (*instance_namespace_parts(path), 'class', *source.symbol.split('::'))))
        module = 'svx_instance_' + stem
        instance = 'svx_export_' + '_'.join(map(_scope_component, source.symbol.split('::')))
        parameters = [('SVXSourceType', source),
                      *((f'SVXBaseType_{index}', owner) for index, owner in enumerate(source.base_lineage))]
        value_parameters = [(f'SVXNativeValueType_{index}', value) for index, value in enumerate(local.value_types)
                            if value.source_scope == source.source_scope]
        native_references = {value.symbol: name for name, value in value_parameters}
        if path in local_owners:
            if owner_insertions is None:
                raise SVXInheritanceError('generate class bridges require integrated source copies')
            block = 'svx_local_' + stem
            owner_lines = ['import svx_pkg::*;', 'import svtypes_pkg::*;']
            owner_lines.extend(emit_owner_records(local, source.source_scope))
            inherited = _unbridged_sv_ancestors(source.base_lineage)
            helper = 'SVXInstanceMirror'
            owner_lines.extend(_emit_sv_projection_class(helper, _sv_class_reference(source), source,
                base_methods=source.methods, dispatch_virtuals=_effective_virtual_methods(source, inherited),
                inherited_sv_sources=inherited, is_root_sv_mirror=True))
            registrations = []
            if source.constructor is not None:
                owner_lines.extend(_emit_sv_projection_factory(source, helper, automatic_instance=False))
                registrations.append(f'    register_{helper}_factory();')
            for index, (_, owner) in enumerate(parameters):
                if owner.canonical_id in registered_static or not any(method.is_static for method in owner.methods):
                    continue
                dispatcher = f'static_dispatcher_{index}'
                owner_lines.extend(_emit_sv_static_gateway(owner, source_type=_sv_class_reference(owner),
                    gateway_name=f'StaticGateway_{index}', dispatcher_name=f'StaticDispatcher_{index}',
                    instance_name=dispatcher, automatic_instance=False))
                registrations.append(f'    {dispatcher} = new();')
                registered_static.add(owner.canonical_id)
            owner_lines.extend(['function automatic void initialize();', *registrations, 'endfunction', ''])
            key = path + '.' + block
            owner_lines.extend(emit_owner_initializer(key, owner_root=(owner_roots or {}).get(path, path), owner_path=path))
            owner_insertions.setdefault(path, []).append({'name': block, 'text': '\n'.join(owner_lines)})
            bindings.append({'class_id': source.canonical_id, 'instance_path': path,
                             'bridge_kind': 'program' if container == 'program' and (owner_roots or {}).get(path) == path else 'generate',
                             'bridge_instance': block, 'initialization_key': key})
            if container != 'program':
                bindings[-1]['initialize'] = '$root.' + key + '.initialize'
            continue
        lines.extend([f'{container} {module} #(',
                      ',\n'.join(f'  parameter type {name}' for name, _ in (*parameters, *value_parameters)),
                      ');', 'import svx_pkg::*;', 'import svtypes_pkg::*;'])
        bound_source = bind_owner_types(source, native_references)
        record_manifest = replace(local, classes=(bound_source,))
        if container == 'interface':
            def without_statics(owner):
                return replace(owner, methods=tuple(method for method in owner.methods if not method.is_static),
                               base_lineage=tuple(without_statics(parent) for parent in owner.base_lineage))
            record_manifest = replace(local, classes=(without_statics(bound_source),))
        lines.extend(emit_owner_records(record_manifest, source.source_scope, native_references=native_references))
        ancestors = tuple(replace(owner, symbol=name, specialization=None)
                          for (name, _), owner in zip(parameters[1:], bound_source.base_lineage))
        native = replace(bound_source, symbol='SVXSourceType', specialization=None, base_lineage=ancestors)
        inherited = _unbridged_sv_ancestors(ancestors)
        helper = 'SVXInstanceMirror'
        projection = (replace(native, methods=tuple(method for method in native.methods if not method.is_static))
                      if container == 'interface' else native)
        lines.extend(_emit_sv_projection_class(helper, 'SVXSourceType', projection,
            base_methods=projection.methods, dispatch_virtuals=_effective_virtual_methods(projection, inherited),
            inherited_sv_sources=inherited, is_root_sv_mirror=True))
        registrations = []
        if source.constructor is not None:
            lines.extend(_emit_sv_projection_factory(native, helper, automatic_instance=False))
            registrations.append(f'    register_{helper}_factory();')
        static_owners = [(name, owner) for name, owner in parameters
                         if owner.canonical_id not in registered_static
                         and any(method.is_static for method in owner.methods)]
        static_initialize = None
        if container == 'interface' and static_owners:
            if owner_insertions is None:
                raise SVXInheritanceError('interface static bridges require integrated source copies; use svx export or source integration')
            block = 'svx_static_' + stem
            owner_lines = ['import svx_pkg::*;', 'import svtypes_pkg::*;']
            static_records = replace(local, classes=tuple(
                replace(owner, fields=(), base_lineage=(),
                        methods=tuple(method for method in owner.methods if method.is_static))
                for _, owner in static_owners))
            owner_lines.extend(emit_owner_records(static_records, source.source_scope))
            owner_registrations = []
            for index, (_, owner) in enumerate(static_owners):
                dispatcher = f'static_dispatcher_{index}'
                owner_lines.extend(_emit_sv_static_gateway(owner, source_type=_sv_class_reference(owner),
                    gateway_name=f'StaticGateway_{index}', dispatcher_name=f'StaticDispatcher_{index}',
                    instance_name=dispatcher, automatic_instance=False))
                owner_registrations.append(f'    {dispatcher} = new();')
            owner_lines.extend(['function automatic void initialize();', *owner_registrations,
                                'endfunction', ''])
            owner_lines.extend(emit_owner_initializer(path + '.' + block,
                owner_root=(owner_roots or {}).get(path, path), owner_path=path))
            owner_insertions.setdefault(path, []).append({'name': block, 'text': '\n'.join(owner_lines)})
            static_initialize = '$root.' + path + '.' + block + '.initialize'
        else:
            for index, (name, owner) in enumerate(static_owners):
                dispatcher = f'svx_instance_static_dispatcher_{index}'
                lines.extend(_emit_sv_static_gateway(bind_owner_types(owner, native_references), source_type=name,
                    gateway_name=f'SVXInstanceStaticGateway_{index}', dispatcher_name=f'SVXInstanceStaticDispatcher_{index}',
                    instance_name=dispatcher, automatic_instance=False))
                registrations.append(f'    {dispatcher} = new();')
        registered_static.update(owner.canonical_id for _, owner in static_owners)
        key = path + '.' + instance
        lines.extend(['  function automatic void initialize();', *registrations, '  endfunction'])
        lines.extend(emit_owner_initializer(key))
        lines.extend([f'end{container} : {module}',
                      f'bind {path} {module} #(',
                      ',\n'.join([*(f'  .{name}({_sv_class_reference(owner)})' for name, owner in parameters),
                                  *(f'  .{name}({value.symbol})' for name, value in value_parameters)]),
                      f') {instance}();', ''])
        bindings.append({'class_id': source.canonical_id, 'instance_path': path,
                         'bridge_module': module, 'bridge_instance': instance,
                         'bridge_kind': container,
                         'initialize': '$root.' + key + '.initialize', 'initialization_key': key})
        if static_initialize is not None:
            bindings[-1]['static_initialize'] = static_initialize
            bindings[-1]['static_initialization_key'] = static_initialize.removeprefix('$root.').removesuffix('.initialize')
    if metadata is not None:
        metadata['instance_bindings'] = bindings
    return '\n'.join(lines)
