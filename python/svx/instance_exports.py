"""Bind existing generated adapters to a concrete native instance owner."""

from dataclasses import replace

from .errors import SVXInheritanceError
from .owner_records import emit_owner_records, emit_owner_initializer, with_local_call_records, bind_owner_types, owner_value_dependencies
from .scoped_exports import _scope_component
from .source_scopes import instance_namespace_parts
from .value_exports import with_value_types
from .native_handles import with_native_handle_adapters, register_native_handle_alias


@with_value_types(codegen=True)
@with_local_call_records
@with_native_handle_adapters
def emit_instance_export_bridges(manifest, *, metadata=None, owner_insertions=None, local_owners=(), owner_roots=None,
                                 owner_contexts=None):
    from .inheritance import (
        _all_manifest_classes, _effective_virtual_methods, _emit_sv_projection_class,
        _emit_sv_projection_factory, _emit_sv_static_gateway, _generated_sv_header,
        _manifest_handle_bindings, _sv_class_reference, _unbridged_sv_ancestors,
        _handle_adapter_stem, _emit_sv_external_handle_adapters,
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
    registered_adapters = set()
    registered_value_aliases = set()
    for source in classes:
        local = replace(manifest, classes=(source,), callables=())
        if any(owner.language != 'sv' for owner in _all_manifest_classes(local)):
            raise SVXInheritanceError('instance-bound class bridges currently require SV lineage')
        handles = _manifest_handle_bindings(local)
        if any(binding.kind == 'virtual_interface' for binding in handles):
            from .native_handles import uses_generic_handle
            if any(not uses_generic_handle(binding) for binding in handles
                   if binding.kind == 'virtual_interface'):
                raise SVXInheritanceError('instance virtual-interface adapters with nominal call records need owner-local type binding; this layout remains unfinished')
        path = source.source_scope['path']
        container = source.source_scope.get('container', 'module')
        if container == 'program' and path not in local_owners:
            raise SVXInheritanceError('program class bridges require integrated source copies')
        context = (owner_contexts or {}).get(path, {})
        visible_scopes = []
        for owner in source.base_lineage:
            scope = owner.source_scope
            if scope is None or scope == source.source_scope:
                continue
            accessible = ((scope['kind'] == 'compilation_unit' and scope['index'] == context.get('unit'))
                          or (scope['kind'] == 'instance' and scope['path'] in context.get('instances', ())))
            if not accessible:
                raise SVXInheritanceError('instance ancestors from other native owners need explicit type binding; this layout remains unfinished')
            if scope not in visible_scopes:
                visible_scopes.append(scope)
        stem = '_'.join(map(_scope_component, (*instance_namespace_parts(path), 'class', *source.symbol.split('::'))))
        module = 'svx_instance_' + stem
        instance = 'svx_export_' + '_'.join(map(_scope_component, source.symbol.split('::')))
        parameters = [('SVXSourceType', source),
                      *((f'SVXBaseType_{index}', owner) for index, owner in enumerate(source.base_lineage))]
        needed_values = {value.key for value in owner_value_dependencies(local)}
        if needed_values.intersection(context.get('shadowed_values', ())):
            raise SVXInheritanceError('visible owner value types with shadowed native names need qualified alias placement; this layout remains unfinished')
        value_parameters = [(f'SVXNativeValueType_{index}', value) for index, value in enumerate(local.value_types)
                            if value.key in needed_values and value.source_scope in (source.source_scope, *visible_scopes)]
        from .value_exports import native_value_name
        symbols, names = {}, {}
        for _, value in value_parameters:
            name = native_value_name(value.symbol, value.source_scope)
            if ((value.symbol in symbols and symbols[value.symbol] != value.key)
                    or (name in names and names[name] != value.key)):
                raise SVXInheritanceError('visible owner value types with shadowed native names need qualified alias placement; this layout remains unfinished')
            symbols[value.symbol] = names[name] = value.key
        native_references = {value.symbol: name for name, value in value_parameters}
        handle_parameters = [(f'SVXNativeHandleType_{index}', binding)
                             for index, binding in enumerate(handles) if binding.collection_binding is None]
        native_references.update((binding.sv_type, name) for name, binding in handle_parameters)
        local_source = path in local_owners or (container == 'interface' and bool(handles))
        value_arguments = {name: value.symbol for name, value in value_parameters}
        type_arguments = {name: _sv_class_reference(owner) for name, owner in parameters}
        if not local_source:
            for name, owner in parameters[1:]:
                if owner.source_scope is None or owner.source_scope == source.source_scope:
                    continue
                if owner_insertions is None:
                    raise SVXInheritanceError('lexical ancestor bindings require integrated source copies')
                scope = owner.source_scope
                parts = (('unit', str(scope['index']), *owner.symbol.split('::')[1:])
                         if scope['kind'] == 'compilation_unit' else
                         ('instance', *instance_namespace_parts(scope['path']), *owner.symbol.split('::')))
                alias = 'SVXNativeAncestor_' + '_'.join(map(_scope_component, parts))
                type_arguments[name] = alias
                if (path, owner.canonical_id) not in registered_value_aliases:
                    owner_insertions.setdefault(path, []).append({'name': alias,
                        'text': f'typedef {_sv_class_reference(owner)} {alias};', 'lexical_declaration': True})
                    registered_value_aliases.add((path, owner.canonical_id))
            for name, value in value_parameters:
                if '::' not in value.symbol:
                    continue
                if owner_insertions is None:
                    raise SVXInheritanceError('nested owner type arguments require integrated source copies')
                alias = 'SVXNativeValue_' + '_'.join(map(_scope_component, value.symbol.split('::')))
                value_arguments[name] = alias
                if (path, value.symbol) not in registered_value_aliases:
                    owner_insertions.setdefault(path, []).append({'name': alias,
                        'text': f'typedef {value.symbol} {alias};', 'lexical_declaration': True})
                    registered_value_aliases.add((path, value.symbol))
        if handles and local_source:
            if owner_insertions is None:
                raise SVXInheritanceError('scoped class handles require integrated source copies')
            for index, binding in enumerate(handles):
                adapter_stem = _handle_adapter_stem(binding)
                alias = 'SVXScoped_' + adapter_stem
                register_native_handle_alias(binding, alias)
            fresh = tuple(binding for binding in handles
                          if (path, _handle_adapter_stem(binding)) not in registered_adapters)
            if fresh:
                from .source_scopes import instance_class_id
                owner_prefix = instance_class_id(path, 'SVX').rsplit('/', 1)[0] + '/'
                local_bindings = tuple(binding for binding in fresh if local_source
                                       and binding.target_type_name.startswith(owner_prefix))
                shared_bindings = tuple(binding for binding in fresh if binding not in local_bindings)
                declarations = []
                if local_bindings:
                    declarations = _emit_sv_external_handle_adapters(local, package_name=None,
                        bindings=local_bindings, import_call_records=False)
                from .native_handles import generic_handle_specialization
                for binding in shared_bindings:
                    adapter_stem = _handle_adapter_stem(binding)
                    alias = 'SVXScoped_' + adapter_stem
                    native = generic_handle_specialization(binding, adapter_stem)
                    declarations.append(f'typedef {native} {alias};')
                owner_insertions.setdefault(path, []).append({'name': 'SVXScoped_' + _handle_adapter_stem(fresh[0]),
                    'text': '\n'.join(declarations), 'lexical_declaration': True})
                registered_adapters.update((path, _handle_adapter_stem(binding)) for binding in fresh)
        if local_source:
            if owner_insertions is None:
                raise SVXInheritanceError('generate class bridges require integrated source copies')
            block = 'svx_local_' + stem
            owner_lines = ['import svx_pkg::*;', 'import svtypes_pkg::*;']
            enum_packers = {} if (owner_roots or {}).get(path, path) != path else None
            owner_lines.extend(emit_owner_records(local, source.source_scope, local_enum_packers=enum_packers,
                                                 visible_scopes=visible_scopes))
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
            if enum_packers:
                # Rewrite only generator-owned fragments, never original SV.
                for original, replacement in enum_packers.items():
                    owner_lines = [line.replace(original, replacement) for line in owner_lines]
            owner_insertions.setdefault(path, []).append({'name': block, 'text': '\n'.join(owner_lines)})
            bindings.append({'class_id': source.canonical_id, 'instance_path': path,
                             'bridge_kind': container if container in {'program', 'interface'} and (owner_roots or {}).get(path) == path else 'generate',
                             'bridge_instance': block, 'initialization_key': key})
            if container != 'program':
                bindings[-1]['initialize'] = '$root.' + key + '.initialize'
            continue
        lines.extend([f'{container} {module} #(',
                      ',\n'.join(f'  parameter type {name}' for name, _ in (*parameters, *value_parameters, *handle_parameters)),
                      ');', 'import svx_pkg::*;', 'import svtypes_pkg::*;'])
        bound_source = bind_owner_types(source, native_references)
        record_manifest = replace(local, classes=(bound_source,))
        if container == 'interface':
            def without_statics(owner):
                return replace(owner, methods=tuple(method for method in owner.methods if not method.is_static),
                               base_lineage=tuple(without_statics(parent) for parent in owner.base_lineage))
            record_manifest = replace(local, classes=(without_statics(bound_source),))
        lines.extend(emit_owner_records(record_manifest, source.source_scope, native_references=native_references,
                                        visible_scopes=visible_scopes))
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
            owner_lines.extend(emit_owner_records(static_records, source.source_scope, visible_scopes=visible_scopes))
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
                      ',\n'.join([*(f'  .{name}({type_arguments[name]})' for name, owner in parameters),
                                  *(f'  .{name}({value_arguments[name]})' for name, value in value_parameters),
                                  *(f'  .{name}({binding.sv_type})' for name, binding in handle_parameters)]),
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
