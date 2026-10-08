"""Source-copy integration backend for the explicit inheritance-gen output mode."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from types import SimpleNamespace

from .errors import SVXInheritanceError
from .inheritance import (
    Manifest, _emit_planned_sv_root_sv_projection, _emit_sv_projection_factory,
    _emit_sv_static_gateway, _projection_helper_package, _sv_generated_names,
    _sv_root_artifact_portions, _sv_root_construction_plan, _unbridged_sv_ancestors,
    _all_manifest_classes, _manifest_lineage_contexts,
    _python_root_artifact_portions, _python_root_construction_plan,
    _emit_planned_python_root_sv_projection,
    _emit_sv_external_handle_adapters, _manifest_handle_bindings, _handle_adapter_name,
    projection_plans, emit_sv_mirrors,
)
from .sv_scan import _pyslang, _source_class_name, _python_proxy_id
from .sv_source_options import _source_parse_options


def _emit_sv_root_source_unit(manifest: Manifest, source: str, *, predefines=None, undefines=(), include_dirs=()) -> str:
    return _emit_staged_source_unit(manifest, source, portions=_sv_root_artifact_portions(manifest),
                                    construction_plan=_sv_root_construction_plan,
                                    projection_emitter=_emit_planned_sv_root_sv_projection,
                                    predefines=predefines, undefines=undefines, include_dirs=include_dirs)


def _emit_python_root_source_unit(manifest: Manifest, source: str, *, predefines=None, undefines=(), include_dirs=()) -> str:
    return _emit_staged_source_unit(manifest, source, portions=_python_root_artifact_portions(manifest),
                                    construction_plan=_python_root_construction_plan,
                                    projection_emitter=_emit_planned_python_root_sv_projection,
                                    predefines=predefines, undefines=undefines, include_dirs=include_dirs)


def _join_source_units(sources: Mapping[str, str]) -> str:
    """Preserve caller order and the shared preprocessor state of one compile unit."""
    if not sources:
        raise SVXInheritanceError('source integration requires at least one source input')
    fragments = []
    for filename, source in sources.items():
        if not isinstance(filename, str) or not filename or any(char in filename for char in '\r\n\0'):
            raise SVXInheritanceError('source input names must be nonempty single-line paths')
        if not isinstance(source, str):
            raise TypeError('source input contents must be text')
        fragments.append(f'`line 1 {json.dumps(filename, ensure_ascii=False)} 0\n{source}\n')
    return ''.join(fragments)


def _emit_sv_root_source_units(manifest: Manifest, sources: Mapping[str, str], *, predefines=None, undefines=(), include_dirs=()) -> str:
    return _emit_staged_source_unit(manifest, _join_source_units(sources),
                                   portions=_sv_root_artifact_portions(manifest),
                                   construction_plan=_sv_root_construction_plan,
                                   projection_emitter=_emit_planned_sv_root_sv_projection,
                                   source_units=sources, preserve_locations=True,
                                   predefines=predefines, undefines=undefines, include_dirs=include_dirs)


def _emit_python_root_source_units(manifest: Manifest, sources: Mapping[str, str], *, predefines=None, undefines=(), include_dirs=()) -> str:
    return _emit_staged_source_unit(manifest, _join_source_units(sources),
                                   portions=_python_root_artifact_portions(manifest),
                                   construction_plan=_python_root_construction_plan,
                                   projection_emitter=_emit_planned_python_root_sv_projection,
                                   source_units=sources, preserve_locations=True,
                                   predefines=predefines, undefines=undefines, include_dirs=include_dirs)


def _emit_source_units(manifest: Manifest, sources: Mapping[str, str], *, predefines=None, undefines=(), include_dirs=()) -> str:
    """Integrate both logical root languages in one ordered source unit."""
    sv_portions = _sv_root_artifact_portions(manifest)
    python_portions = _python_root_artifact_portions(manifest)
    sv_ids = {portion.canonical_id for portion in sv_portions}

    def construction_plan(source, *, manifest):
        planner = _sv_root_construction_plan if source.canonical_id in sv_ids else _python_root_construction_plan
        return planner(source, manifest=manifest)

    def projection_emitter(manifest, source, *, generated_name, base_type):
        emitter = (_emit_planned_sv_root_sv_projection if source.canonical_id in sv_ids
                   else _emit_planned_python_root_sv_projection)
        return emitter(manifest, source, generated_name=generated_name, base_type=base_type)

    return _emit_staged_source_unit(
        manifest, _join_source_units(sources), portions=(*sv_portions, *python_portions),
        construction_plan=construction_plan, projection_emitter=projection_emitter,
        source_units=sources, preserve_locations=True,
        predefines=predefines, undefines=undefines, include_dirs=include_dirs)


def _inline_active_source_includes(tree, source: str, *, root_buffer=None) -> str:
    """Copy parser-selected physical includes without changing their source files."""
    directives = tree.getIncludeDirectives()
    if not directives:
        return source
    from pyslang import SourceRange

    manager = tree.sourceManager
    includes = {}
    for directive in directives:
        span = directive.syntax.sourceRange
        end = span.end
        # Locate the invocation end, not the filename macro's definition origin.
        while manager.isMacroLoc(end):
            end = manager.getExpansionRange(end).end
        span = SourceRange(span.start, end)
        if span.start.buffer != span.end.buffer or not manager.isFileLoc(span.start):
            raise SVXInheritanceError('source integration needs direct source anchors for include directives')
        includes.setdefault(span.start.buffer, []).append((span, directive.buffer.id))

    def expand(buffer, active):
        if buffer in active:
            raise SVXInheritanceError('recursive source include expansion')
        raw = manager.getSourceText(buffer).removesuffix('\0').encode('utf-8')
        boundary = len(raw)
        for span, child in sorted(includes.get(buffer, ()), key=lambda item: item[0].start.offset, reverse=True):
            start, end = span.start.offset, span.end.offset
            if start > end or end > boundary:
                raise SVXInheritanceError('overlapping source include anchors')
            filename = manager.getRawFileName(child)
            parent = str(manager.getFileName(span.end))
            line = manager.getLineNumber(span.end)
            text = ('\n`line 1 ' + json.dumps(filename, ensure_ascii=False) + ' 0\n' +
                    expand(child, (*active, buffer)) + '\n`line ' + str(line) + ' ' +
                    json.dumps(parent, ensure_ascii=False) + ' 0\n')
            raw = raw[:start] + text.encode('utf-8') + raw[end:]
            boundary = start
        return raw.decode('utf-8')

    return expand(manager.getAllBuffers()[0] if root_buffer is None else root_buffer, ())


def _emit_staged_source_unit(manifest: Manifest, source: str, *, portions, construction_plan, projection_emitter,
                             source_units: Mapping[str, str] | None = None,
                             preserve_locations: bool = True, predefines=None, undefines=(), include_dirs=()) -> str:
    """Insert minimal bridges into a parsed source copy, preserving public aliases.

    Participating SV declarations belong to one compilation unit, optionally
    supplied as ordered source-file texts with explicit macro inputs. Only
    parser-identified proxy names and declaration boundaries are edited;
    user comments, literals and the original file stay untouched.
    """
    from pyslang import DiagnosticEngine, DiagnosticSeverity, SourceManager, SourceRange

    syntax = _pyslang()
    options = _source_parse_options(predefines, undefines, include_dirs, discover_proxies=True)

    def check(parsed):
        engine = DiagnosticEngine(parsed.sourceManager)
        for diagnostic in parsed.diagnostics:
            if engine.getSeverity(diagnostic.code, diagnostic.location) in {
                DiagnosticSeverity.Error, DiagnosticSeverity.Fatal,
            }:
                filename = parsed.sourceManager.getFileName(diagnostic.location)
                line = parsed.sourceManager.getLineNumber(diagnostic.location)
                raise SVXInheritanceError(f'cannot integrate SV source unit {filename}:{line}: {diagnostic.code}')
        return parsed

    def parse(text):
        return check(syntax.SyntaxTree.fromText(text, SourceManager(), options=options))

    if source_units is None:
        tree = parse(source)
        expanded = _inline_active_source_includes(tree, source)
    else:
        # Physical buffer paths control relative includes; `line only controls
        # logical diagnostics. Parse all buffers together to retain macro state.
        manager = SourceManager()
        buffers = {filename: manager.assignText(filename, text)
                   for filename, text in source_units.items()}
        tree = check(syntax.SyntaxTree.fromBuffers(list(buffers.values()), manager, options=options))
        expanded = _join_source_units({
            filename: _inline_active_source_includes(tree, text, root_buffer=buffers[filename].id)
            for filename, text in source_units.items()})
    if source_units is not None or expanded != source:
        source = expanded
        tree = parse(source)
        preserve_locations = True
    main_buffer = tree.sourceManager.getAllBuffers()[0]

    def restore_location(location):
        if not preserve_locations:
            return ''
        filename = str(tree.sourceManager.getFileName(location))
        line = tree.sourceManager.getLineNumber(location)
        return f'`line {line} {json.dumps(filename, ensure_ascii=False)} 0\n'

    def generated_location(name):
        return f'`line 1 {json.dumps("svx-generated/" + name + ".sv")} 0\n' if preserve_locations else ''

    def direct_span(span):
        if span.start.buffer != main_buffer or span.end.buffer != main_buffer:
            raise SVXInheritanceError('source integration needs direct source anchors; macro-generated declaration anchors remain unfinished')
        return span.start.offset, span.end.offset

    def expanded_span(location):
        manager = tree.sourceManager
        while manager.isMacroLoc(location):
            span = manager.getExpansionRange(location)
            location = span.start
        return location

    macro_tokens = None

    def base_span(base):
        nonlocal macro_tokens
        span = base.sourceRange
        if span.start.buffer == main_buffer and span.end.buffer == main_buffer:
            return direct_span(span)
        manager = tree.sourceManager
        start = expanded_span(span.start)
        end = span.end
        while manager.isMacroLoc(end):
            end = manager.getExpansionRange(end).end
        if start.buffer != main_buffer or end.buffer != main_buffer:
            return direct_span(span)
        tokens = set()
        base.visit(lambda item: tokens.add((item.location.buffer, item.location.offset))
                   if type(item).__name__ == 'Token' else None)
        if macro_tokens is None:
            macro_tokens = []
            tree.root.visit(lambda item: macro_tokens.append(item)
                            if type(item).__name__ == 'Token' and manager.isMacroLoc(item.location) else None)

        # Replacing an invocation must not discard other syntax emitted by it.
        for item in macro_tokens:
            location = expanded_span(item.location)
            if (location.buffer == main_buffer and start.offset <= location.offset < end.offset
                    and (item.location.buffer, item.location.offset) not in tokens):
                raise SVXInheritanceError('base macro must expand only to the declared proxy type')
        return start.offset, end.offset

    roots = [tree.root] if hasattr(tree.root, 'header') else list(tree.root.members)
    classes = {}
    proxy_markers = {}
    proxy_anchors = {}
    type_declarations = {}
    occupied = {}
    packages = {}
    for node in roots:
        if str(node.kind) != 'SyntaxKind.PackageDeclaration':
            continue
        package = str(node.header.name).strip()
        if package in packages:
            raise SVXInheritanceError(f'duplicate source package {package}')
        packages[package] = node
        direct_span(node.sourceRange)
        names = occupied.setdefault(package, set())
        def reserve(member):
            name = str(getattr(member, 'name', '')).strip()
            if name.isidentifier():
                names.add(name)
        node.visit(reserve)
        for member in node.members:
            proxy_id = _python_proxy_id(member) if type(member).__name__ == 'ClassDeclarationSyntax' else None
            if proxy_id is not None:
                proxy_symbol = package + '::' + str(member.name).strip()
                if proxy_symbol in proxy_markers:
                    raise SVXInheritanceError(f'duplicate source Proxy marker {proxy_symbol}')
                proxy_markers[proxy_symbol] = proxy_id
                start = expanded_span(member.sourceRange.start)
                end = member.sourceRange.end
                while tree.sourceManager.isMacroLoc(end):
                    end = tree.sourceManager.getExpansionRange(end).end
                anchor = SimpleNamespace(sourceRange=SourceRange(start, end))
                direct_span(anchor.sourceRange)
                proxy_anchors[proxy_symbol] = (package, anchor)
                continue
            forward_class = (type(member).__name__ == 'ForwardTypedefDeclarationSyntax'
                             and str(member.typeRestriction).strip() == 'class')
            if type(member).__name__ in {'ClassDeclarationSyntax', 'TypedefDeclarationSyntax'} or forward_class:
                type_symbol = package + '::' + str(member.name).strip()
                type_declarations.setdefault(type_symbol, (package, member))
            if type(member).__name__ == 'ClassDeclarationSyntax':
                symbol = package + '::' + str(member.name).strip()
                direct_span(member.sourceRange)
                if symbol in classes:
                    raise SVXInheritanceError(f'duplicate source class {symbol}')
                classes[symbol] = (package, member)

    independent = tuple(plan.lineage[-1] for plan in projection_plans(manifest) if not plan.steps)
    if not portions and not independent:
        raise SVXInheritanceError('source integration requires a cross-language target of the selected root language')
    if not packages:
        raise SVXInheritanceError('source integration requires a source package anchor')
    for target in independent:
        if target.language == 'sv' and target.symbol not in classes:
            raise SVXInheritanceError(f'source unit lacks required declaration {target.symbol}')
    final_package = max(packages.values(), key=lambda node: node.sourceRange.end.offset)
    final_location = final_package.sourceRange.end
    independent_anchors = {}
    for target in independent:
        if target.language != 'python':
            continue
        public = _projection_helper_package(target, 'proxy') + '::' + target.name
        uses = []
        for package, node in packages.items():
            for member in node.members:
                references = []
                def select_reference(candidate):
                    if (type(candidate).__name__ == 'ScopedNameSyntax'
                            and _source_class_name(candidate) == public):
                        references.append(candidate)
                member.visit(select_reference)
                if references:
                    uses.append((package, member))
        if uses:
            package, member = min(uses, key=lambda item: direct_span(item[1].sourceRange)[0])
            requested = '_svx_proxy_' + target.name
            helper = _sv_generated_names(occupied[package], (requested,))[requested]
            occupied[package].add(helper)
            independent_anchors[public] = (package, member, helper)
    declarations = _all_manifest_classes(manifest)
    contexts = _manifest_lineage_contexts(manifest)
    plans = {portion.canonical_id: construction_plan(portion, manifest=manifest) for portion in portions}
    anchors = {}
    names = {}
    for portion in portions:
        plan = plans[portion.canonical_id]
        if portion.language == 'sv':
            symbol = portion.symbol
            position = 'after'
        else:
            candidates = [item for item in declarations if item.language == 'sv'
                          and contexts.get(item.canonical_id)
                          and contexts[item.canonical_id][-1].canonical_id == portion.canonical_id]
            target = min(candidates, key=lambda item: classes[item.symbol][1].sourceRange.start.offset
                         if item.symbol in classes else float('inf'), default=None)
            if target is None:
                raise SVXInheritanceError(f'missing source anchor after Python portion {portion.canonical_id}')
            symbol, position = target.symbol, 'before'
        marker = None
        if portion.language == 'python':
            markers = [symbol for symbol, class_id in proxy_markers.items()
                       if class_id == portion.canonical_id]
            if markers:
                marker = min(markers, key=lambda symbol: direct_span(proxy_anchors[symbol][1].sourceRange)[0])
        if marker is not None:
            package, node = proxy_anchors[marker]
        elif symbol not in classes:
            raise SVXInheritanceError(f'source unit lacks required declaration {symbol}')
        else:
            package, node = classes[symbol]
        requested = '_svx_' + ('mirror_' if portion.language == 'sv' else 'proxy_') + portion.name
        used = occupied[package]
        while True:
            name = _sv_generated_names(used, (requested,))[requested]
            if not any(name + suffix in used for suffix in ('_factory', '_factory_instance')):
                break
            used.add(name)
        used.update((name, name + '_factory', name + '_factory_instance'))
        names[portion.canonical_id] = name
        anchors[portion.canonical_id] = (package, node, position)

    edits = []
    aliases = {}
    alias_offsets = {}
    endpoint_references = {}
    source_endpoint_references = {}
    endpoint_names = {}
    bindings = _manifest_handle_bindings(manifest)
    consumers = {}
    for portion in portions:
        context = replace(portion, base_lineage=plans[portion.canonical_id].ancestors)
        local = _manifest_handle_bindings(replace(manifest, classes=(context,)))
        package, node, position = anchors[portion.canonical_id]
        offset = direct_span(node.sourceRange)[0 if position == 'before' else 1]
        for binding in local:
            consumers.setdefault(binding.target_type_name, []).append((package, offset))
    for target in independent:
        local = _manifest_handle_bindings(replace(manifest, classes=(target,)))
        public = (_projection_helper_package(target, 'proxy') + '::' + target.name
                  if target.language == 'python' else None)
        anchor = independent_anchors.get(public)
        consumer = ((anchor[0], direct_span(anchor[1].sourceRange)[0]) if anchor else
                    (str(final_package.header.name).strip(), final_location.offset))
        for binding in local:
            consumers.setdefault(binding.target_type_name, []).append(consumer)
    public_endpoint_names = set()
    for binding in bindings:
        uses = consumers.get(binding.target_type_name, [])
        if not uses:
            continue
        public = _handle_adapter_name(binding)
        if public in public_endpoint_names:
            raise SVXInheritanceError(f'conflicting public external adapter name {public}')
        public_endpoint_names.add(public)
        if binding.kind == 'sv_class' and binding.sv_type in type_declarations:
            owner, declaration = type_declarations[binding.sv_type]
            direct_span(declaration.sourceRange)
            location = declaration.sourceRange.end
        else:
            owner = min(uses, key=lambda item: item[1])[0]
            location = packages[owner].header.sourceRange.end
        for consumer, offset in uses:
            ready = location.offset if consumer == owner else packages[owner].sourceRange.end.offset
            if ready > offset:
                raise SVXInheritanceError(
                    f'external endpoint {binding.target_type_name} depends on a source type declared after its consumer')
        used = occupied[owner]
        requested = '_svx_' + public
        while True:
            private = _sv_generated_names(used, (requested,))[requested]
            if private + 'Endpoint' not in used:
                break
            used.add(private)
        used.update((private, private + 'Endpoint'))
        endpoint_names[binding.target_type_name] = private
        body = _emit_sv_external_handle_adapters(
            manifest, package_name=None, bindings=(binding,), adapter_names=endpoint_names)
        edits.append((location.offset, location.offset,
                      '\n' + generated_location(private) + '\n'.join(body) + '\n' + restore_location(location)))
        endpoint_references[public] = owner + '::' + private
        for suffix in ('', 'Endpoint'):
            source_endpoint_references['svx_external_handles_pkg::' + public + suffix] = (
                owner + '::' + private + suffix, owner, location.offset)
        aliases.setdefault('svx_external_handles_pkg', []).extend([
            f'  typedef {owner}::{private} {public};',
            f'  typedef {owner}::{private}Endpoint {public}Endpoint;'])
        end = packages[owner].sourceRange.end
        previous = alias_offsets.get('svx_external_handles_pkg')
        if previous is None or end.offset > previous.offset:
            alias_offsets['svx_external_handles_pkg'] = end

    def qualify_endpoint_calls(lines):
        if not endpoint_references:
            return lines
        prefix = 'package _svx_endpoint_calls;\n'
        text = prefix + '\n'.join(lines) + '\nendpackage'
        parsed = parse(text)
        substitutions = {}
        def select(node):
            if type(node).__name__ == 'ScopedNameSyntax':
                replacement = endpoint_references.get(_source_class_name(node.left))
                if replacement is not None:
                    span = node.left.sourceRange
                    substitutions[(span.start.offset, span.end.offset)] = replacement
        parsed.root.visit(select)
        raw = text.encode('utf-8')
        for (start, end), replacement in sorted(substitutions.items(), reverse=True):
            raw = raw[:start] + replacement.encode('utf-8') + raw[end:]
        return raw.decode('utf-8').removeprefix(prefix).removesuffix('\nendpackage').splitlines()

    static_owners = set()
    for portion in sorted(portions, key=lambda item: (len(plans[item.canonical_id].ancestors), item.canonical_id)):
        plan = plans[portion.canonical_id]
        package, node, position = anchors[portion.canonical_id]
        helper = names[portion.canonical_id]
        if portion.language == 'sv':
            base = portion.symbol
        elif portion.canonical_id == plan.root.canonical_id and plan.root.language == 'python':
            base = None
        else:
            parent = next(item for item in reversed(plan.ancestors) if item.language == 'sv')
            parent_package = anchors[parent.canonical_id][0]
            base = ('' if parent_package == package else parent_package + '::') + names[parent.canonical_id]
            parent_anchor = anchors[parent.canonical_id][1]
            ready = (direct_span(parent_anchor.sourceRange)[1] if parent_package == package
                     else packages[parent_package].sourceRange.end.offset)
            if ready > direct_span(node.sourceRange)[0]:
                raise SVXInheritanceError(
                    f'Proxy {portion.canonical_id} precedes its SV base definition {parent.symbol}')
        body = projection_emitter(manifest, portion, generated_name=helper, base_type=base)
        if portion.language == 'sv':
            body.extend(_emit_sv_projection_factory(portion, helper, announce_receiver=True))
            for owner in (*_unbridged_sv_ancestors(plan.ancestors), portion):
                if owner.canonical_id in static_owners or not any(method.is_static for method in owner.methods):
                    continue
                private = _sv_generated_names(occupied[package], (
                    helper + '_static_gateway', helper + '_static_dispatch', helper + '_static_instance'))
                occupied[package].update(private.values())
                body.extend(_emit_sv_static_gateway(owner, gateway_name=private[helper + '_static_gateway'],
                                                   dispatcher_name=private[helper + '_static_dispatch'],
                                                   instance_name=private[helper + '_static_instance']))
                static_owners.add(owner.canonical_id)
        elif any(method.is_static for method in portion.methods):
            private = _sv_generated_names(occupied[package], (
                helper + '_static_gateway', helper + '_static_dispatch', helper + '_static_instance'))
            occupied[package].update(private.values())
            body.extend(_emit_sv_static_gateway(
                portion, source_type=helper, inherit_source=False,
                gateway_name=private[helper + '_static_gateway'],
                dispatcher_name=private[helper + '_static_dispatch'],
                instance_name=private[helper + '_static_instance']))
        body = qualify_endpoint_calls(body)
        start, end = direct_span(node.sourceRange)
        offset = end if position == 'after' else start
        imports = '  import svx_pkg::*;\n  import svtypes_pkg::*;\n  import svx_call_records_pkg::*;\n'
        location = node.sourceRange.end if position == 'after' else node.sourceRange.start
        edits.append((offset, offset, '\n' + generated_location(helper) + imports + '\n'.join(body) + '\n' + restore_location(location)))
        public_package = _projection_helper_package(portion, 'mirror' if portion.language == 'sv' else 'proxy')
        aliases.setdefault(public_package, []).append(f'  typedef {package}::{helper} {portion.name};')
        package_end = packages[package].sourceRange.end
        previous = alias_offsets.get(public_package)
        if previous is None or package_end.offset > previous.offset:
            alias_offsets[public_package] = package_end

    emitted_marker_aliases = set()
    for declaration in declarations:
        context = contexts.get(declaration.canonical_id, ())
        if declaration.language != 'sv' or not context or context[-1].language != 'python':
            continue
        parent = context[-1]
        if declaration.symbol not in classes:
            raise SVXInheritanceError(f'source unit lacks required declaration {declaration.symbol}')
        package, node = classes[declaration.symbol]
        expected = _projection_helper_package(parent, 'proxy') + '::' + parent.name
        clause = node.extendsClause
        actual_base = _source_class_name(clause.baseName) if clause is not None else None
        marker_symbol = (actual_base if actual_base is not None and '::' in actual_base
                         else package + '::' + str(actual_base))
        marker_id = proxy_markers.get(marker_symbol)
        if actual_base != expected and marker_id != parent.canonical_id:
            raise SVXInheritanceError(f'{declaration.symbol} must derive from its declared Python proxy {expected}')
        parent_package = anchors[parent.canonical_id][0]
        parent_anchor = anchors[parent.canonical_id][1]
        ready = (direct_span(parent_anchor.sourceRange)[0] if parent_package == package
                 else packages[parent_package].sourceRange.end.offset)
        if ready > direct_span(node.sourceRange)[0]:
            raise SVXInheritanceError(f'{declaration.symbol} precedes its Python Proxy definition')
        replacement = ('' if parent_package == package else parent_package + '::') + names[parent.canonical_id]
        edits.append((*base_span(clause.baseName), replacement))
        if marker_id is not None and marker_symbol not in emitted_marker_aliases:
            marker_package, marker_name = marker_symbol.split('::')
            marker_node = proxy_anchors[marker_symbol][1]
            offset = direct_span(marker_node.sourceRange)[0]
            alias_type = ('' if marker_package == parent_package else parent_package + '::') + names[parent.canonical_id]
            alias_ready = (direct_span(parent_anchor.sourceRange)[0] if marker_package == parent_package
                           else packages[parent_package].sourceRange.end.offset)
            if alias_ready > offset:
                raise SVXInheritanceError(f'Proxy marker {marker_symbol} precedes its generated helper')
            edits.append((offset, offset, f'\n  typedef {alias_type} {marker_name};\n'))
            emitted_marker_aliases.add(marker_symbol)

    # Public alias packages follow their source packages. References inside the
    # owning package must use the already inserted local helper instead.
    proxy_references = {}
    proxy_definition_offsets = {}
    for public, (package, anchor, helper) in independent_anchors.items():
        proxy_references.setdefault(package, {})[public] = helper
        proxy_definition_offsets[(package, public)] = direct_span(anchor.sourceRange)[0]
    for portion in portions:
        if portion.language == 'python':
            package, anchor, _position = anchors[portion.canonical_id]
            public = _projection_helper_package(portion, 'proxy') + '::' + portion.name
            proxy_references.setdefault(package, {})[public] = names[portion.canonical_id]
            proxy_definition_offsets[(package, public)] = direct_span(anchor.sourceRange)[0]
    replaced = {(start, end) for start, end, _replacement in edits if start != end}
    for package, replacements in proxy_references.items():
        forward = set()
        def rewrite_reference(node):
            if type(node).__name__ != 'ScopedNameSyntax':
                return
            replacement = replacements.get(_source_class_name(node))
            if replacement is None:
                return
            span = base_span(node)
            if span[0] < proxy_definition_offsets[(package, _source_class_name(node))]:
                forward.add(replacement)
            if span not in replaced:
                edits.append((*span, replacement))
                replaced.add(span)
        packages[package].visit(rewrite_reference)
        if forward:
            location = packages[package].header.sourceRange.end
            text = '\n' + generated_location(package + '_forward')
            text += '\n'.join('  typedef class ' + name + ';' for name in sorted(forward))
            text += '\n' + restore_location(location)
            edits.append((location.offset, location.offset, text))

    qualified_proxies = {public: (package, helper)
                         for package, replacements in proxy_references.items()
                         for public, helper in replacements.items()}
    def rewrite_foreign_package_proxy(node):
        if type(node).__name__ != 'ScopedNameSyntax':
            return
        public = _source_class_name(node)
        target = qualified_proxies.get(public)
        if target is None:
            return
        owner, helper = target
        span = base_span(node)
        if span in replaced:
            return
        alias_ready = (final_location if public in independent_anchors else
                       alias_offsets.get(public.split('::')[0]))
        if alias_ready is not None and span[0] >= alias_ready.offset:
            return
        if span[0] < packages[owner].sourceRange.end.offset:
            raise SVXInheritanceError(
                f'source proxy reference {_source_class_name(node)} precedes its owning package {owner}')
        edits.append((*span, owner + '::' + helper))
        replaced.add(span)
    tree.root.visit(rewrite_foreign_package_proxy)

    def rewrite_public_endpoint_reference(node):
        if type(node).__name__ != 'ScopedNameSyntax':
            return
        endpoint = source_endpoint_references.get(_source_class_name(node))
        if endpoint is None:
            return
        replacement, owner, local_ready = endpoint
        span = base_span(node)
        package_node = packages[owner]
        same_package = package_node.sourceRange.start.offset <= span[0] < package_node.sourceRange.end.offset
        ready = local_ready if same_package else package_node.sourceRange.end.offset
        if span[0] < ready:
            raise SVXInheritanceError('source external adapter reference precedes its concrete owner definition')
        if span not in replaced:
            edits.append((*span, replacement))
            replaced.add(span)
    tree.root.visit(rewrite_public_endpoint_reference)

    if independent:
        # Reuse the public renderer, but own common records/endpoints only once.
        standalone = emit_sv_mirrors(replace(manifest, classes=independent))
        standalone_tree = parse(standalone)
        standalone_bytes = standalone.encode('utf-8')
        nodes = ([standalone_tree.root] if hasattr(standalone_tree.root, 'header')
                 else standalone_tree.root.members)
        for node in nodes:
            if str(node.kind) != 'SyntaxKind.PackageDeclaration':
                continue
            package = str(node.header.name).strip()
            if package in {'svx_call_records_pkg', 'svx_external_handles_pkg'}:
                continue
            members = []
            for member in node.members:
                start, end = member.sourceRange.start.offset, member.sourceRange.end.offset
                text = standalone_bytes[start:end].decode('utf-8')
                public = package + '::' + str(getattr(member, 'name', '')).strip()
                anchor = independent_anchors.get(public)
                if anchor and type(member).__name__ == 'ClassDeclarationSyntax':
                    owner, source_member, helper = anchor
                    substitutions = [(member.name.range, helper)]
                    if member.endBlockName is not None:
                        substitutions.append((member.endBlockName.name.range, helper))
                    raw_member = standalone_bytes[start:end]
                    for span, replacement in sorted(substitutions, key=lambda item: item[0].start.offset, reverse=True):
                        a, b = span.start.offset - start, span.end.offset - start
                        raw_member = raw_member[:a] + replacement.encode('utf-8') + raw_member[b:]
                    body_lines = qualify_endpoint_calls(raw_member.decode('utf-8').splitlines())
                    location = source_member.sourceRange.start
                    imports = '  import svx_pkg::*;\n  import svtypes_pkg::*;\n  import svx_call_records_pkg::*;\n'
                    edits.append((direct_span(source_member.sourceRange)[0],
                                  direct_span(source_member.sourceRange)[0],
                                  '\n' + generated_location(helper) + imports + '\n'.join(body_lines)
                                  + '\n' + restore_location(location)))
                    text = f'  typedef {owner}::{helper} {str(member.name).strip()};'
                members.append(text)
            body = '\n'.join(members)
            combined = aliases.setdefault(package, [])
            existing = parse('package _svx_members;\n' + '\n'.join(combined) + '\nendpackage')
            existing_package = (existing.root if hasattr(existing.root, 'header')
                                else existing.root.members[0])
            existing_names = {str(member.name).strip() for member in existing_package.members
                              if hasattr(member, 'name')}
            for member in node.members:
                name = str(getattr(member, 'name', '')).strip()
                if name and name in existing_names:
                    raise SVXInheritanceError(f'conflicting generated public member {package}::{name}')
            combined.append(body)
            alias_offsets[package] = final_location

    for package, body in sorted(aliases.items()):
        location = alias_offsets[package]
        declarations = ['\n' + generated_location(package),
                        '// Public bridge declarations and type aliases.',
                        f'package {package};', *body, f'endpackage : {package}']
        edits.append((location.offset, location.offset, '\n'.join(declarations) + '\n' + restore_location(location)))
    raw = source.encode('utf-8')
    boundary = len(raw) + 1
    ordered = sorted(enumerate(edits), key=lambda item: (item[1][0], item[1][1], item[0]), reverse=True)
    for _index, (start, end, replacement) in ordered:
        if end > boundary:
            raise SVXInheritanceError('overlapping source integration anchors')
        raw = raw[:start] + replacement.encode('utf-8') + raw[end:]
        boundary = start
    return raw.decode('utf-8')
