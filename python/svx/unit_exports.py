"""Owner-local bridges for native compilation-unit classes.

The caller inserts this code in the original compilation unit, after its class
declarations. A package wrapper would change which native types it can access.
"""

from dataclasses import replace
import json

from .errors import SVXInheritanceError
from .inheritance import (
    _all_manifest_classes, _effective_virtual_methods, _emit_sv_projection_class,
    _emit_sv_projection_factory, _emit_sv_static_gateway, _generated_sv_header,
    _sv_class_reference, _unbridged_sv_ancestors, projection_plans,
)
from .scoped_exports import _scope_component
from .value_exports import with_value_types
from .owner_records import emit_owner_records, with_local_call_records


@with_value_types(codegen=True)
@with_local_call_records
def emit_unit_export_bridge(manifest, index, *, metadata=None):
    """Render one owner's direct class targets with the existing runtime ABI."""
    if type(index) is not int or index < 0:
        raise SVXInheritanceError('compilation-unit bridge index must be nonnegative')
    if any(plan.steps for plan in projection_plans(manifest)):
        raise SVXInheritanceError('owner-local unit bridge currently requires direct SV class targets')
    classes = tuple(cls for cls in manifest.classes
                    if cls.source_scope == {'kind': 'compilation_unit', 'index': index})
    if not classes:
        return ''
    if any(cls.language != 'sv' for cls in _all_manifest_classes(manifest)):
        raise SVXInheritanceError('owner-local unit bridge requires SV lineage')
    owners = {owner.canonical_id: owner for cls in classes for owner in (*cls.base_lineage, cls)}
    for owner in owners.values():
        if owner.source_scope is not None and owner.source_scope != {'kind': 'compilation_unit', 'index': index}:
            raise SVXInheritanceError('a unit class cannot inherit a class from an independent compilation unit')
    local = replace(manifest, classes=classes, callables=())
    from .inheritance import _manifest_handle_bindings
    if _manifest_handle_bindings(local):
        raise SVXInheritanceError('unit class handle adapters need owner-local adapter placement; this layout remains unfinished')
    lines = [*_generated_sv_header(manifest), '',
             '// These declarations remain in the original compilation unit.',
             'import svx_pkg::*;', 'import svtypes_pkg::*;']
    lines.extend(emit_owner_records(local, {'kind': 'compilation_unit', 'index': index}))
    registrations = []
    registered_static = set()
    for source in classes:
        helper = 'svx_unit_mirror_' + str(index) + '_' + '_'.join(map(_scope_component, source.symbol.split('::')[1:]))
        ancestors = _unbridged_sv_ancestors(source.base_lineage)
        lines.extend(_emit_sv_projection_class(
            helper, _sv_class_reference(source), source,
            base_methods=source.methods,
            dispatch_virtuals=_effective_virtual_methods(source, ancestors),
            inherited_sv_sources=ancestors, is_root_sv_mirror=True))
        if source.constructor is not None:
            lines.extend(_emit_sv_projection_factory(source, helper))
            registrations.append('    register_' + helper + '_factory();')
        for ordinal, owner in enumerate((*ancestors, source)):
            if owner.canonical_id in registered_static or not any(method.is_static for method in owner.methods):
                continue
            stem = helper if owner is source else helper + f'_ancestor_{ordinal}'
            instance = stem + '_static_dispatcher'
            lines.extend(_emit_sv_static_gateway(
                owner, source_type=helper if owner is source else _sv_class_reference(owner),
                inherit_source=owner is not source,
                gateway_name=stem + 'StaticGateway',
                dispatcher_name=stem + 'StaticDispatcher', instance_name=instance))
            registrations.append(f'    {instance} = new();')
            registered_static.add(owner.canonical_id)
    startup = f'svx_unit_exports_{index}'
    lines.extend(['', f'module {startup};',
                  '  function automatic void initialize();', *registrations,
                  '  endfunction', f'endmodule : {startup}', ''])
    if metadata is not None:
        metadata['registration_module'] = startup
        metadata['registration_method'] = 'initialize'
    return '\n'.join(lines)


def emit_unit_integrated_sources(manifest, sources, *, compilation_unit=False,
                                startup_metadata=None, predefines=None, undefines=(), include_dirs=()):
    """Preserve original unit grouping and explicitly link each owner's factory."""
    from pathlib import Path
    from pyslang import SourceManager
    from pyslang.ast import Compilation
    from .source_layout import (
        _inline_active_source_includes, _join_source_units, _emit_staged_source_unit,
        integrated_source_paths,
    )
    from .inheritance import _sv_root_construction_plan, _emit_planned_sv_root_sv_projection
    from .sv_frontend import elaborate_sources
    from .sv_library_search import load_libraries
    from .sv_scan import _check_source_diagnostics, _pyslang, _lookup_sv_symbol, _declaration_source_symbol
    from .sv_source_options import _source_parse_options

    if any(source.language != 'sv' for source in manifest.classes) or any(
            plan.steps for plan in projection_plans(manifest)):
        raise SVXInheritanceError('alternating compilation-unit source integration needs owner-local lineage placement; this layout remains unfinished')
    from .sv_frontend import source_elaboration_mode
    instance_targets = tuple(source for source in manifest.classes
                             if source.source_scope is not None and source.source_scope['kind'] == 'instance')
    if instance_targets and source_elaboration_mode() == 'packages':
        raise SVXInheritanceError('instance-owned exports require design hierarchy elaboration; use --sv-elaboration all')
    _join_source_units(sources)
    options = _source_parse_options(predefines, undefines, include_dirs, discover_proxies=True)
    manager = SourceManager()
    buffers = {filename: manager.assignText(filename, text) for filename, text in sources.items()}
    groups = [tuple(sources)] if compilation_unit else [(filename,) for filename in sources]
    trees = []
    for group in groups:
        tree = _pyslang().SyntaxTree.fromBuffers([buffers[name] for name in group], manager, options=options)
        _check_source_diagnostics(tree, group[0])
        trees.append((Path(group[0]), tree))
    validation_trees = tuple(tree for _, tree in load_libraries(
        trees, tuple(map(Path, sources)), manager, options, compilation_unit))
    compilation = Compilation()
    for tree in validation_trees:
        compilation.addSyntaxTree(tree)
    compilation = elaborate_sources(compilation)
    local_owners = set()
    owner_roots = {}
    for source in manifest.classes:
        raw = {'symbol': source.symbol, 'source_scope': source.source_scope}
        actual = _lookup_sv_symbol(compilation, _declaration_source_symbol(raw))
        if actual is None or not getattr(actual, 'canonicalType', None) or not actual.canonicalType.isClass:
            raise SVXInheritanceError(f'source units lack required class declaration {source.symbol}')
        if (source.source_scope is not None and source.source_scope['kind'] == 'compilation_unit'
                and source.source_scope['index'] >= len(groups)):
            raise SVXInheritanceError('unit class owner was loaded from a library; provide its original source as an explicit build input for source-copy integration')
        if source.source_scope is not None and source.source_scope['kind'] == 'instance':
            from .source_scopes import native_scope_chain, lookup_native_scope
            owner = lookup_native_scope(compilation, source.source_scope['path'])
            scopes = native_scope_chain(compilation, source.source_scope['path'])
            container = scopes[0].definition.definitionKind.name.lower()
            owner_roots[source.source_scope['path']] = scopes[0].hierarchicalPath
            if owner.kind.name == 'GenerateBlock' or container == 'program':
                local_owners.add(source.source_scope['path'])
            if source.source_scope.get('container', 'module') != container:
                raise SVXInheritanceError(f'instance source_scope.container does not match native {container} owner at {source.source_scope["path"]}')
    if any(definition.name == 'svx_exports' for definition in compilation.getDefinitions()):
        raise SVXInheritanceError('original design already defines reserved generated module svx_exports')

    from .instance_exports import emit_instance_export_bridges
    instance_metadata = {}
    owner_insertions = {}
    instance_bridges = emit_instance_export_bridges(manifest, metadata=instance_metadata,
                                                   owner_insertions=owner_insertions, local_owners=local_owners,
                                                   owner_roots=owner_roots)
    definitions = {definition.name for definition in compilation.getDefinitions()}
    for binding in instance_metadata.get('instance_bindings', ()):
        from .source_scopes import lookup_native_scope
        owner = lookup_native_scope(compilation, binding['instance_path'])
        if (binding.get('bridge_module') in definitions
                or getattr(owner, 'body', owner).lookupName(binding['bridge_instance']) is not None):
            raise SVXInheritanceError(f'instance export generated name collides with original design at {binding["instance_path"]}')
    reachable_buffers = {buffer.id for buffer in buffers.values()}
    reachable_buffers.update(directive.buffer.id for _, tree in trees for directive in tree.getIncludeDirectives())
    from .source_scopes import native_scope_insertions
    insertions = native_scope_insertions(compilation, owner_insertions, manager=manager,
                                         reachable_buffers=reachable_buffers)

    package_manifest = replace(manifest, classes=tuple(source for source in manifest.classes if source.source_scope is None))
    has_package_bridge = bool(package_manifest.classes or package_manifest.callables)
    package_anchor = None
    for index, (_, tree) in enumerate(trees):
        roots = (tree.root,) if str(tree.root.kind) == 'SyntaxKind.PackageDeclaration' else getattr(tree.root, 'members', ())
        if any(str(node.kind) == 'SyntaxKind.PackageDeclaration' for node in roots):
            package_anchor = index
    if has_package_bridge and package_anchor is None:
        package_anchor = 0

    paths = integrated_source_paths(sources, compilation_unit=compilation_unit)
    emitted = {}
    unit_modules = []
    package_metadata = {}
    for index, (output, group, (_, tree)) in enumerate(zip(paths, groups, trees)):
        originals = {name: _inline_active_source_includes(tree, sources[name], root_buffer=buffers[name].id,
                                                        insertions=insertions) for name in group}
        if index == package_anchor:
            if any(str(node.kind) == 'SyntaxKind.PackageDeclaration'
                   for node in ((tree.root,) if str(tree.root.kind) == 'SyntaxKind.PackageDeclaration' else getattr(tree.root, 'members', ()))):
                text = _emit_staged_source_unit(
                    package_manifest, _join_source_units(originals), portions=(),
                    construction_plan=_sv_root_construction_plan,
                    projection_emitter=_emit_planned_sv_root_sv_projection,
                    source_units=originals, complete_sv_bridge=True, validation_sources=validation_trees,
                    startup_metadata=package_metadata, predefines=predefines, undefines=undefines, include_dirs=include_dirs)
            else:
                from .source_layout import emit_sv_export_bridge
                text = ('// Generated by svx inheritance-gen. Do not edit.\n'
                        + emit_sv_export_bridge(package_manifest, metadata=package_metadata) + '\n'
                        + _join_source_units(originals))
        else:
            text = ('// Generated by svx inheritance-gen. Do not edit.\n'
                    + _join_source_units(originals))
        metadata = {}
        bridge = emit_unit_export_bridge(manifest, index, metadata=metadata)
        if bridge:
            text += '\n`line 1 ' + json.dumps(f'svx-generated/unit-{index}.sv') + ' 0\n' + bridge
            unit_modules.append(metadata['registration_module'])
        emitted[output] = text
    startup_task = any(source.source_scope['container'] == 'program' for source in instance_targets)
    startup_kind = 'task' if startup_task else 'function'
    lines = ['// Generated by svx inheritance-gen. Do not edit.',
             '// Instantiate once in the testbench and initialize after svx_init().',
             instance_bridges, 'module svx_exports;']
    for index, name in enumerate(unit_modules):
        lines.append(f'  {name} unit_{index}();')
    lines.append('  task automatic initialize();' if startup_task else '  function automatic void initialize();')
    if package_metadata.get('systemverilog_startup'):
        lines.append('    ' + package_metadata['systemverilog_startup'] + '();')
    lines.extend(f'    unit_{index}.initialize();' for index in range(len(unit_modules)))
    initialize = 'wait_initialize_owner' if startup_task else 'initialize_owner'
    for binding in instance_metadata.get('instance_bindings', ()):
        for field in ('initialization_key', 'static_initialization_key'):
            if field in binding:
                lines.append(f'    svx_pkg::svx_inheritance_registry::{initialize}({json.dumps(binding[field])});')
    lines.extend(['  end' + startup_kind, 'endmodule : svx_exports', ''])
    emitted['exports.sv'] = '\n'.join(lines)
    if startup_metadata is not None:
        startup_metadata['systemverilog_startup_module'] = {'module': 'svx_exports', 'method': 'initialize'}
        if startup_task:
            startup_metadata['systemverilog_startup_module']['timing'] = 'task'
        startup_metadata.update(instance_metadata)
    return emitted
