"""SystemVerilog source facts used to validate inheritance declarations.

This module deliberately does not infer SvTypes codecs from SV spelling. SVX
uses SvTypes declarations as its only call-data contract; the source scanner
only establishes language facts that must agree with that contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import json
import re
from typing import Callable, Iterable

from .errors import SVXInheritanceError
from .sv_frontend import (_analysis, analysis_source_manager, elaborate_sources, compile_source_trees,
                          source_elaboration_mode)
from .sv_instance_scan import with_instance_discovery


@dataclass(frozen=True)
class SVClassFact:
    """The source-level facts relevant to one SystemVerilog class."""

    symbol: str
    direct_base: str | None
    virtual_methods: frozenset[str]
    static_methods: frozenset[str]
    parameter_kinds: tuple[str, ...] = ()
    methods: tuple[SVInterfaceMemberFact, ...] = ()
    fields: tuple[SVClassFieldFact, ...] = ()
    constructor: SVInterfaceMemberFact | None = None
    python_proxy_id: str | None = None


@dataclass(frozen=True)
class SVClassFieldFact:
    name: str
    sv_type: str
    qualifiers: frozenset[str]
    has_dimensions: bool


@dataclass(frozen=True)
class SVInterfaceParameterFact:
    name: str
    direction: str
    sv_type: str


@dataclass(frozen=True)
class SVInterfaceMemberFact:
    """One signal, task, or function declared by an SV interface."""

    name: str
    kind: str
    sv_type: str | None = None
    parameters: tuple[SVInterfaceParameterFact, ...] = ()


@dataclass(frozen=True)
class SVModportMemberFact:
    name: str
    direction: str


@dataclass(frozen=True)
class SVVirtualInterfaceFact:
    """One interface type that may occur behind a ``virtual interface`` handle.

    The manifest generator needs the static interface and modport identity to
    generate a restricted Python view. This is source-fact collection only:
    it does not invent a call-data codec or require a second VIF whitelist.
    """

    symbol: str
    modports: frozenset[str]
    members: tuple[SVInterfaceMemberFact, ...] = ()
    modport_members: tuple[tuple[str, tuple[SVModportMemberFact, ...]], ...] = ()

    def visible_members(self, modport: str | None) -> tuple[SVInterfaceMemberFact, ...]:
        """Return members visible through ``virtual interface[.modport]``."""

        if modport is None:
            return self.members
        for name, visible in self.modport_members:
            if name == modport:
                visible_names = {member.name for member in visible}
                return tuple(member for member in self.members if member.name in visible_names)
        raise SVXInheritanceError(
            f"SystemVerilog interface {self.symbol} has no modport {modport}"
        )


def _pyslang():
    try:
        from pyslang import syntax
    except ImportError as error:
        raise SVXInheritanceError(
            "SV source scanning requires the optional 'pyslang' dependency; "
            "install SVX with the 'manifest' extra"
        ) from error
    return syntax


def _method_name(item: object) -> str | None:
    declaration = getattr(item, "declaration", None)
    prototype = getattr(declaration, "prototype", getattr(item, "prototype", None))
    name = getattr(prototype, "name", None)
    if name is None:
        return None
    result = _token_text(name)
    return result if result and result != "new" else None


def _python_proxy_id(member: object) -> str | None:
    for attribute in getattr(member, "attributes", ()):
        for spec in getattr(attribute, "specs", ()):
            if str(getattr(spec, "name", "")).strip() != "__svx_discovery_python_class_id":
                continue
            literal = getattr(getattr(getattr(spec, "value", None), "expr", None), "literal", None)
            value = getattr(literal, "valueText", None)
            if not isinstance(value, str) or not value.startswith("py://"):
                raise SVXInheritanceError("SVX_PY_PROXY requires a literal canonical Python class ID")
            return value
    return None


def _parse_source(syntax: object, path: Path, source_manager=None, *, parse_options=None):
    from pyslang import SourceManager

    # The default source manager caches file contents across discovery calls.
    options = {} if parse_options is None else {"options": parse_options}
    tree = syntax.SyntaxTree.fromFile(str(path), source_manager or SourceManager(), **options)
    _check_source_diagnostics(tree, path)
    return tree


def _check_source_diagnostics(tree, path):
    from pyslang import DiagnosticEngine, DiagnosticSeverity
    engine = DiagnosticEngine(tree.sourceManager)
    for diagnostic in tree.diagnostics:
        if engine.getSeverity(diagnostic.code, diagnostic.location) in {
            DiagnosticSeverity.Error, DiagnosticSeverity.Fatal,
        }:
            filename = tree.sourceManager.getFileName(diagnostic.location)
            line = tree.sourceManager.getLineNumber(diagnostic.location)
            raise SVXInheritanceError(
                f"cannot parse SystemVerilog source {filename or path}:{line}: {diagnostic.code}"
            )


def _with_python_proxy_members(tree, declarations):
    """Supply semantic-only members for parser-identified Proxy placeholders."""
    from .inheritance import (_parse_field, _parse_method, _sv_field_declaration, _sv_parameters,
                              _sv_return_type, _sv_collection_typedef)

    foreign = {item["canonical_id"]: item for item in declarations}
    changed = False

    def portions(declaration, visiting=()):
        class_id = declaration["canonical_id"]
        if class_id in visiting:
            raise SVXInheritanceError(f"cyclic Python Proxy declarations at {class_id}")
        if not declaration.get("mirror_base_ids"):
            for parent_id in declaration.get("python_base_ids", []):
                if parent_id in foreign:
                    yield from portions(foreign[parent_id], (*visiting, class_id))
            if not declaration.get("python_base_ids"):
                lineage = declaration.get("base_lineage", [])
                start = next((index + 1 for index in range(len(lineage) - 1, -1, -1)
                              if lineage[index].get("language") == "sv"), 0)
                yield from lineage[start:]
        yield declaration

    def member_text(node):
        nonlocal changed
        class_id = _python_proxy_id(node) if type(node).__name__ == "ClassDeclarationSyntax" else None
        if class_id is None or class_id not in foreign:
            return str(node)
        changed = True
        methods = {}
        fields = {}
        for declaration in portions(foreign[class_id]):
            for field in declaration.get("fields", []):
                fields[field["name"]] = _parse_field(field, f"Proxy {class_id}.{field['name']}")
            for method in declaration.get("methods", []):
                methods[method["name"]] = _parse_method(method, declaration["canonical_id"], f"Proxy {class_id}.{method['name']}")
        base = _source_class_name(node.extendsClause.baseName)
        lines = [f'(* __svx_discovery_python_class_id = "{class_id}" *)',
                 f"{'virtual ' if any(method.pure_virtual for method in methods.values()) else ''}class {node.name} extends {base};"]
        lines.extend(_sv_field_declaration(field) + ";" for field in fields.values())
        aliases = {}
        for method in methods.values():
            bindings = [parameter.type_binding for parameter in method.parameters if parameter.handle is None]
            if method.return_type is not None and method.return_handle is None:
                bindings.append(method.return_type)
            for binding in bindings:
                declaration = _sv_collection_typedef(binding)
                if declaration is not None:
                    aliases[declaration[0]] = declaration[1]
        lines.extend(aliases.values())
        for method in methods.values():
            qualifier = "static " if method.is_static else "pure virtual " if method.pure_virtual else "virtual " if method.virtual else ""
            prototype = (f"{qualifier}task {method.name}({_sv_parameters(method, qualified=False)});" if method.timing == "task"
                         else f"{qualifier}function {_sv_return_type(method, qualified=False)} {method.name}({_sv_parameters(method, qualified=False)});")
            lines.append(prototype)
            if not method.pure_virtual:
                lines.append("endtask" if method.timing == "task" else "endfunction")
        lines.append("endclass")
        return "\n".join(lines)

    roots = [tree.root] if hasattr(tree.root, "header") else list(tree.root.members)
    rendered = []
    for node in roots:
        if str(node.kind) == "SyntaxKind.PackageDeclaration":
            rendered.append(str(node.header))
            rendered.extend(member_text(member) for member in node.members)
            rendered.append("endpackage")
        else:
            rendered.append(str(node))
    if not changed:
        return tree
    result = _pyslang().SyntaxTree.fromText("\n".join(rendered), tree.sourceManager)
    _check_source_diagnostics(result, "Python Proxy discovery scaffold")
    return result


def _python_proxy_context(declarations):
    context = {}
    for declaration in declarations:
        for item in (declaration, *declaration.get("base_lineage", [])):
            # Handle normalization also accepts partial contract declarations;
            # only canonical class declarations can supply Proxy scaffolding.
            if item.get("language") == "python" and item.get("canonical_id"):
                context[item["canonical_id"]] = item
    return tuple(context.values())


def _parse_sources(syntax, paths, source_manager=None, *, parse_options=None, compilation_unit=False,
                   proxy_context=()):
    from time import perf_counter
    from .sv_library_search import _search

    paths = tuple(paths)
    if not paths:
        return
    source_manager = source_manager or analysis_source_manager()
    state = _analysis.get()
    shared = state is not None and source_manager is state.source_manager
    search = _search.get()
    key = (tuple(str(path) for path in paths), id(parse_options), compilation_unit,
           id(search), source_elaboration_mode())
    if shared and key in state.trees:
        trees = state.trees[key]
        state.syntax_reuses += 1
    else:
        start = perf_counter()
        trees = tuple(_parse_source_batch(syntax, paths, source_manager,
                                         parse_options=parse_options, compilation_unit=compilation_unit))
        if shared:
            state.trees[key] = trees
            # Trees and library parser storage must outlive every semantic probe.
            # Retain option/search identities too, preventing object-id reuse.
            state.owners.append((parse_options, search))
            state.parse_batches += 1
            state.parse_seconds += perf_counter() - start
    # Proxy members depend on Python discovery context, not just SV source.
    # Never reuse a transformed tree for a different set of Python declarations.
    for path, tree in trees:
        yield path, _with_python_proxy_members(tree, proxy_context) if proxy_context else tree


def _parse_source_batch(syntax, paths, source_manager, *, parse_options, compilation_unit):
    trees = []
    if compilation_unit:
        options = {} if parse_options is None else {"options": parse_options}
        tree = syntax.SyntaxTree.fromFiles([str(path) for path in paths],
                                          source_manager, **options)
        _check_source_diagnostics(tree, paths[0])
        trees.append((paths[0], tree))
    else:
        for path in paths:
            tree = _parse_source(syntax, path, source_manager, parse_options=parse_options)
            trees.append((path, tree))
    from .sv_library_search import load_libraries
    from .source_selection import record_source_trees
    record_source_trees(trees)
    yield from load_libraries(trees, paths, source_manager, parse_options, compilation_unit)


def _token_text(token: object) -> str:
    identifier = getattr(token, 'identifier', None)
    if identifier is not None:
        return _token_text(identifier)
    return str(getattr(token, "valueText", token)).strip()


def _is_virtual(item: object) -> bool:
    return any(
        _token_text(qualifier) == "virtual"
        for qualifier in getattr(item, "qualifiers", ())
    )


def _is_static(item: object) -> bool:
    return any(
        _token_text(qualifier) == "static"
        for qualifier in getattr(item, "qualifiers", ())
    )


def _declarator_type(sv_type: str, declarator: object) -> str:
    dimensions = "".join(str(item).strip() for item in getattr(declarator, "dimensions", ()))
    return sv_type + (" " + dimensions if dimensions else "")


def _method_fact(item: object, *, include_constructor: bool = False) -> SVInterfaceMemberFact | None:
    declaration = getattr(item, "declaration", item)
    prototype = getattr(declaration, "prototype", None)
    name = _token_text(getattr(prototype, "name", ""))
    if not name or (name == "new" and not include_constructor):
        return None
    is_task = _token_text(getattr(prototype, "keyword", "")) == "task"
    parameters: list[SVInterfaceParameterFact] = []
    direction = "input"
    sv_type = "logic"
    for port in getattr(getattr(prototype, "portList", None), "ports", ()):
        parameter_name = _token_text(getattr(getattr(port, "declarator", None), "name", ""))
        if not parameter_name:
            continue
        # A new explicit direction starts a new type group (default logic).
        # Only an omitted direction carries the preceding type forward.
        explicit_direction = _token_text(getattr(port, "direction", None) or "")
        if explicit_direction:
            direction = explicit_direction
            sv_type = "logic"
        sv_type = str(getattr(port, "dataType", None) or "").strip() or sv_type
        parameters.append(SVInterfaceParameterFact(
            parameter_name, direction, _declarator_type(sv_type, port.declarator)
        ))
    if getattr(prototype, "portList", None) is None:
        for port in getattr(declaration, "items", ()):
            if port.__class__.__name__ != "PortDeclarationSyntax":
                continue
            header = port.header
            direction = _token_text(getattr(header, "direction", None) or "input")
            sv_type = str(getattr(header, "dataType", None) or "logic").strip()
            for declarator in getattr(port, "declarators", ()):
                parameter_name = _token_text(getattr(declarator, "name", ""))
                if parameter_name:
                    parameters.append(SVInterfaceParameterFact(
                        parameter_name, direction, _declarator_type(sv_type, declarator)
                    ))
    return SVInterfaceMemberFact(
        name, "task" if is_task else "function",
        None if is_task else str(getattr(prototype, "returnType", "")).strip(),
        tuple(parameters),
    )


def _source_class_name(node: object) -> str:
    if node.__class__.__name__ == "ScopedNameSyntax":
        return _source_class_name(node.left) + "::" + _source_class_name(node.right)
    identifier = getattr(node, "identifier", None)
    return _token_text(identifier) if identifier is not None else str(node).strip()


def _source_lineage(fact: SVClassFact, facts: dict[str, SVClassFact]) -> tuple[SVClassFact, ...]:
    chain: list[SVClassFact] = []
    seen: set[str] = set()
    while fact is not None:
        if fact.symbol in seen:
            raise SVXInheritanceError(f"cyclic source inheritance involving {fact.symbol}")
        seen.add(fact.symbol)
        chain.append(fact)
        base = fact.direct_base
        if base is None:
            break
        parent_symbol = base if "::" in base else fact.symbol.rsplit("::", 1)[0] + "::" + base
        fact = facts.get(parent_symbol)
    return tuple(chain)


def _unit_scope(symbol):
    owner, _, tail = symbol.partition('::')
    match = re.fullmatch(r'\$unit\[([0-9]+)\]', owner)
    return (int(match[1]), tail) if match else None


def _source_class_id(symbol):
    instance = _instance_scope(symbol)
    if instance is not None:
        from .source_scopes import instance_class_id
        return instance_class_id(*instance)
    unit = _unit_scope(symbol)
    return ('sv://unit/' + str(unit[0]) + '/' + unit[1].replace('::', '/')
            if unit else 'sv://' + symbol.replace('::', '/'))


def _source_class_selector(class_id):
    path = class_id.removeprefix('sv://').split('/')
    if len(path) >= 3 and path[0] == 'unit' and path[1].isdigit():
        return '$unit[' + path[1] + ']::' + '::'.join(path[2:])
    return '::'.join(path)


def _instance_scope(symbol):
    match = re.fullmatch(r'\$instance\[(.*)\]::(.*)', symbol)
    return match.groups() if match else None


def _source_display_name(symbol):
    instance = _instance_scope(symbol)
    return instance[0] + '.' + instance[1] if instance is not None else symbol


def _has_instance_named_values(value, owner=None):
    if isinstance(value, dict):
        reference = value.get('sv')
        if (owner is not None and isinstance(reference, str)
                and re.fullmatch(r'[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*', reference)):
            native = owner
            for component in reference.split('::'):
                if native is not None and native.kind.name == 'TypeAlias' and native.canonicalType.isClass:
                    native = native.canonicalType
                find = getattr(native, 'find', None)
                native = find(component) if find is not None else None
                if native is None:
                    break
            if native is not None and native.kind.name == 'TypeAlias' and not native.canonicalType.isClass:
                return True
        return any(_has_instance_named_values(item, owner) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_has_instance_named_values(item, owner) for item in value)
    return isinstance(value, str) and value.startswith('svx_mirror_instance.')


def _class_fact(symbol, member, *, concrete_alias=False):
    extends = getattr(member, 'extendsClause', None)
    methods = tuple(method for item in member.items
                    if (method := _method_fact(item)) is not None)
    return SVClassFact(
        symbol, _source_class_name(extends.baseName) if extends is not None else None,
        frozenset(name for item in member.items if _is_virtual(item)
                  and (name := _method_name(item)) is not None),
        frozenset(name for item in member.items if _is_static(item)
                  and (name := _method_name(item)) is not None),
        () if concrete_alias else tuple('type' if parameter.__class__.__name__ == 'TypeParameterDeclarationSyntax'
            else 'value' for parameter in getattr(getattr(member, 'parameters', None), 'declarations', ())
            for declarator in getattr(parameter, 'declarators', ()) if _token_text(getattr(declarator, 'name', ''))),
        methods,
        tuple(SVClassFieldFact(_token_text(declarator.name), ' '.join(str(item.declaration.type).split()),
                              frozenset(_token_text(value) for value in item.qualifiers),
                              bool(getattr(declarator, 'dimensions', ())))
              for item in member.items if item.__class__.__name__ == 'ClassPropertyDeclarationSyntax'
              and item.declaration.__class__.__name__ == 'DataDeclarationSyntax'
              for declarator in item.declaration.declarators if _token_text(getattr(declarator, 'name', ''))),
        next((method for item in member.items
              if (method := _method_fact(item, include_constructor=True)) is not None and method.name == 'new'), None),
        _python_proxy_id(member))


def _declaration_source_symbol(declaration):
    symbol = declaration.get('symbol')
    scope = declaration.get('source_scope')
    if isinstance(scope, dict) and scope.get('kind') == 'compilation_unit':
        return f"$unit[{scope['index']}]::" + symbol.removeprefix('$unit::')
    if isinstance(scope, dict) and scope.get('kind') == 'instance':
        return f"$instance[{scope['path']}]::" + symbol
    return symbol


def _semantic_class_selector(actual):
    """Use the actual declaring scope, not an assumed package prefix."""
    node = getattr(actual, 'syntax', None)
    while node is not None:
        if str(node.kind) == 'SyntaxKind.PackageDeclaration':
            return actual.lexicalPath
        if str(node.kind) in {'SyntaxKind.ModuleDeclaration', 'SyntaxKind.InterfaceDeclaration',
                              'SyntaxKind.ProgramDeclaration', 'SyntaxKind.GenerateBlock'}:
            from .sv_instance_scan import semantic_instance_selector
            return semantic_instance_selector(actual)
        node = node.parent
    parent = getattr(actual, 'parentScope', None)
    if parent is not None:
        unit = parent.compilationUnit
        for index, candidate in enumerate(parent.compilation.getRoot().compilationUnits):
            if candidate == unit:
                return f'$unit[{index}]::' + actual.lexicalPath
    return actual.lexicalPath


def scan_sv_sources(paths: Iterable[Path], *, allow_no_packages: bool = False, parse_options=None,
                    compilation_unit=False, proxy_context=()) -> dict[str, SVClassFact]:
    """Parse SV package classes with pyslang and return inheritance facts.

    Inputs may be separate parse units or one ordered shared compilation unit.
    Full project libraries / independent unit groups still require a build-file
    frontend; this scanner never substitutes a regex approximation.
    """

    syntax = _pyslang()
    facts: dict[str, SVClassFact] = {}
    paths = tuple(paths)
    trees = tuple(_parse_sources(syntax, paths, parse_options=parse_options,
                                 compilation_unit=compilation_unit, proxy_context=proxy_context))
    aliases = []

    def class_members(scope, members):
        for member in members:
            declaration = getattr(member, 'declaration', member)
            if type(declaration).__name__ == 'TypedefDeclarationSyntax':
                qualifiers = {_token_text(value) for value in getattr(member, 'qualifiers', ())}
                if not qualifiers & {'local', 'protected'}:
                    aliases.append((scope, _token_text(declaration.name)))
            if type(member).__name__ == 'ClassDeclarationSyntax':
                symbol = scope + '::' + _token_text(member.name)
                yield symbol, member
                yield from class_members(symbol, member.items)

    for unit_index, (path, tree) in enumerate(trees):
        roots = [tree.root]
        if tree.root.kind not in {syntax.SyntaxKind.PackageDeclaration, syntax.SyntaxKind.ClassDeclaration}:
            roots = list(getattr(tree.root, "members", ()))
        scopes = [(f'$unit[{unit_index}]', roots)]
        package_count = 0
        for root in roots:
            if root.kind != syntax.SyntaxKind.PackageDeclaration:
                continue
            package_name = _token_text(getattr(getattr(root, "header", None), "name", ""))
            if not package_name:
                continue
            package_count += 1
            scopes.append((package_name, getattr(root, 'members', ())))
        for scope, members in scopes:
            for symbol, member in class_members(scope, members):
                if symbol in facts:
                    raise SVXInheritanceError(
                        f"duplicate SystemVerilog class definition {symbol}"
                    )
                facts[symbol] = _class_fact(symbol, member)
        if not package_count and not allow_no_packages:
            raise SVXInheritanceError(
                f"SystemVerilog source {path} must contain a package declaration"
            )
    imported_bases = [fact for fact in facts.values()
                      if fact.direct_base and fact.direct_base not in facts
                      and ('::' in fact.direct_base or
                           fact.symbol.rsplit('::', 1)[0] + '::' + fact.direct_base not in facts)]
    if aliases or imported_bases:
        from pyslang.ast import Compilation
        compilation = Compilation()
        for _, tree in trees:
            compilation.addSyntaxTree(tree)
        compilation = compile_source_trees(compilation.getSyntaxTrees())
        alias_sources = {}
        for package_name, alias in aliases:
            member = _lookup_sv_symbol(compilation, package_name + '::' + alias)
            actual = getattr(member, "canonicalType", None)
            if actual is None or not actual.isClass:
                continue
            actual_symbol = _semantic_class_selector(actual)
            source = facts.get(actual_symbol)
            if source is not None:
                alias_symbol = f"{package_name}::{alias}"
                alias_sources[alias_symbol] = actual_symbol
                facts[alias_symbol] = replace(source, symbol=alias_symbol, parameter_kinds=())
        # Import lookup returns the declaring symbol, including named typedefs;
        # a short base name need not belong to the derived class's package.
        for fact in imported_bases:
            scope_name = fact.symbol.rsplit('::', 1)[0]
            scope = _lookup_sv_symbol(compilation, scope_name)
            base = scope.lookupName(fact.direct_base) if scope is not None else None
            resolved = _semantic_class_selector(base) if base is not None and getattr(base, 'canonicalType', None) and base.canonicalType.isClass else None
            if resolved in facts:
                facts[fact.symbol] = replace(fact, direct_base=resolved)
        for alias_symbol, source_symbol in alias_sources.items():
            facts[alias_symbol] = replace(facts[source_symbol], symbol=alias_symbol, parameter_kinds=())
    from .sv_instance_scan import active_instance_facts
    facts.update(active_instance_facts(paths, parse_options, compilation_unit))
    return facts


def _lookup_sv_symbol(compilation, symbol):
    instance = re.fullmatch(r'\$instance\[(.*)\]::(.*)', symbol)
    if instance:
        from .source_scopes import lookup_native_scope
        owner = lookup_native_scope(compilation, instance[1])
        scope = getattr(owner, 'body', owner)
        return (scope.lookupName(instance[2]) if instance[2] else scope) if scope is not None and hasattr(scope, 'lookupName') else None
    unit = _unit_scope(symbol)
    if unit is not None:
        units = compilation.getRoot().compilationUnits
        if unit[0] >= len(units):
            return None
        scope = units[unit[0]]
        return scope.lookupName(unit[1]) if unit[1] else scope
    package, _, member = symbol.partition('::')
    scope = compilation.getPackage(package)
    return scope.lookupName(member) if scope is not None and member else scope


def _compile_owner_probes(compilation, unit_probes, manager, parse_options, source_units, proxy_context=(),
                          scope_probes=None):
    """Keep unit-local type checks in their original semantic compilation unit.

    Reparse only owners needing checks from their original buffers and options.
    Printing preprocessed syntax would lose compiler directives such as
    timescale and change package parameters/types. These are analysis-only
    trees; emitted source copies also preserve the original input context.
    """
    if not unit_probes and not scope_probes:
        return elaborate_sources(compilation)
    from pyslang.ast import Compilation
    from .source_layout import _inline_active_source_includes
    from .source_scopes import native_scope_insertions

    insertions = (native_scope_insertions(elaborate_sources(compilation), scope_probes, manager=manager, guarded=False)
                  if scope_probes else {})

    checked = Compilation()
    for index, tree in enumerate(compilation.getSyntaxTrees()):
        paths = source_units.get(index, ())
        buffers = [manager.readSource(str(path), library=tree.sourceLibrary) for path in paths]
        root_buffers = [buffer.id if buffer is not None else None for buffer in buffers]
        if insertions:
            candidates = []
            for location in (tree.root.sourceRange.start, tree.root.sourceRange.end):
                while manager.isMacroLoc(location):
                    location = manager.getExpansionRange(location).start
                candidates.append(location.buffer)
            for directive in tree.getIncludeDirectives():
                candidates.extend((directive.syntax.sourceRange.start.buffer, directive.buffer.id))
            candidates.extend(insertions)
            by_path = {}
            known_buffers = set(manager.getAllBuffers())
            for buffer in candidates:
                if buffer not in known_buffers:
                    continue
                filename = manager.getFullPath(buffer)
                if filename:
                    by_path.setdefault(Path(filename).resolve(), buffer)
            root_buffers = [by_path.get(Path(path).resolve(), buffer) for path, buffer in zip(paths, root_buffers)]
        active_buffers = set(root_buffers)
        active_buffers.update(directive.buffer.id for directive in tree.getIncludeDirectives())
        local_checks = bool(active_buffers.intersection(insertions))
        if index in unit_probes or local_checks:
            if any(buffer is None for buffer in buffers):
                raise SVXInheritanceError(f'cannot read compilation-unit {index} inputs for owner-local checks')
            if local_checks:
                buffers = [manager.assignText(str(path) + f'.svx-probe-{len(manager.getAllBuffers())}',
                    '`line 1 ' + json.dumps(str(path), ensure_ascii=False) + ' 0\n'
                    + _inline_active_source_includes(tree, manager.getSourceText(buffer).removesuffix('\0'),
                        root_buffer=buffer, insertions=insertions), library=tree.sourceLibrary)
                    for path, buffer in zip(paths, root_buffers)]
            if index in unit_probes:
                buffers.append(manager.assignText(f'<svx-owner-checks-{index}>', '\n'.join(unit_probes[index]) + '\n',
                                                  library=tree.sourceLibrary))
            tree = _pyslang().SyntaxTree.fromBuffers(buffers, manager,
                **({} if parse_options is None else {'options': parse_options}))
            _check_source_diagnostics(tree, f'compilation-unit {index} type checks')
            if proxy_context:
                tree = _with_python_proxy_members(tree, proxy_context)
        checked.addSyntaxTree(tree)
    return elaborate_sources(checked)


def scan_sv_virtual_interfaces(paths: Iterable[Path], *, parse_options=None, compilation_unit=False) -> dict[str, SVVirtualInterfaceFact]:
    """Parse interface declarations and their declared modports with pyslang.

    An interface may live at compilation-unit scope, so its VIF spelling is
    its source name (for example ``bus_if.master``), unlike a package class
    whose spelling is ``pkg::Class``. Generated VIF adapters use this fact to
    reject an unknown modport before generated SV is compiled.
    """

    syntax = _pyslang()
    facts: dict[str, SVVirtualInterfaceFact] = {}
    for path, tree in _parse_sources(syntax, paths, parse_options=parse_options, compilation_unit=compilation_unit):
        roots = (
            [tree.root] if str(tree.root.kind) == "SyntaxKind.InterfaceDeclaration"
            else getattr(tree.root, "members", ())
        )
        for member in roots:
            if str(getattr(member, "kind", "")) != "SyntaxKind.InterfaceDeclaration":
                continue
            header = getattr(member, "header", None)
            name = _token_text(getattr(header, "name", ""))
            if not name:
                raise SVXInheritanceError(
                    f"SystemVerilog interface in {path} has no name"
                )
            modports: set[str] = set()
            modport_members: list[tuple[str, tuple[SVModportMemberFact, ...]]] = []
            members: list[SVInterfaceMemberFact] = []
            for item in getattr(member, "members", ()):
                if item.__class__.__name__ == "DataDeclarationSyntax":
                    sv_type = str(getattr(item, "type", "")).strip()
                    for declarator in getattr(item, "declarators", ()):
                        declarator_name = _token_text(getattr(declarator, "name", ""))
                        if declarator_name:
                            members.append(
                                SVInterfaceMemberFact(
                                    declarator_name, "signal", _declarator_type(sv_type, declarator)
                                )
                            )
                    continue
                if item.__class__.__name__ == "FunctionDeclarationSyntax":
                    method = _method_fact(item)
                    if method is not None:
                        members.append(method)
                    continue
                if item.__class__.__name__ != "ModportDeclarationSyntax":
                    continue
                for modport in getattr(item, "items", ()):
                    modport_name = _token_text(getattr(modport, "name", ""))
                    if not modport_name:
                        raise SVXInheritanceError(
                            f"SystemVerilog interface {name} has an unnamed modport"
                        )
                    if modport_name in modports:
                        raise SVXInheritanceError(
                            f"SystemVerilog interface {name} declares modport "
                            f"{modport_name} more than once"
                        )
                    modports.add(modport_name)
                    visible: dict[str, str] = {}
                    for group in getattr(modport, "ports", ()):
                        if not group.__class__.__name__.startswith("Modport"):
                            continue
                        direction = _token_text(
                            getattr(group, "direction", getattr(group, "importExport", ""))
                        )
                        for port in getattr(group, "ports", ()):
                            port_name = _token_text(getattr(port, "name", ""))
                            if port_name:
                                visible[port_name] = direction
                    modport_members.append(
                        (
                            modport_name,
                            tuple(
                                SVModportMemberFact(member_name, direction)
                                for member_name, direction in sorted(visible.items())
                            ),
                        )
                    )
            if name in facts:
                raise SVXInheritanceError(
                    f"duplicate SystemVerilog interface definition {name}"
                )
            member_names = [member.name for member in members]
            if len(member_names) != len(set(member_names)):
                raise SVXInheritanceError(
                    f"SystemVerilog interface {name} declares duplicate member names"
                )
            facts[name] = SVVirtualInterfaceFact(
                name,
                frozenset(modports),
                tuple(members),
                tuple(modport_members),
            )
    return facts


def discover_sv_class_declarations(
    paths: Iterable[Path], class_ids: Iterable[str],
    binding: Callable[..., dict], *, parse_options=None, compilation_unit=False,
    existing: Iterable[dict] = (),
    python_context: Iterable[dict] = (),
    member_patterns: Iterable[str] = (),
    exclude_member_patterns: Iterable[str] = (),
    value_exports=None,
) -> list[dict]:
    """Collect requested source ancestors, using the caller's SvTypes bindings.

    Returned classes are discovery context, not generation requests. Explicit
    declarations remain the caller's responsibility and override this context.
    """
    paths = tuple(paths)
    python_context = tuple(python_context)
    member_patterns = tuple(member_patterns)
    exclude_member_patterns = tuple(exclude_member_patterns)
    from fnmatch import fnmatchcase

    def selected_member(symbol, name):
        spellings = {name, symbol + '.' + name, _source_display_name(symbol) + '.' + name}
        matches = lambda pattern: any(fnmatchcase(spelling, pattern) for spelling in spellings)
        return ((not member_patterns or any(matches(pattern) for pattern in member_patterns))
                and not any(matches(pattern) for pattern in exclude_member_patterns))
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=python_context)
    from pyslang.ast import Compilation, MethodFlags

    from .sv_instance_scan import active_instance_analysis
    instance_analysis = active_instance_analysis(paths, parse_options, compilation_unit)
    if instance_analysis is not None:
        compilation = instance_analysis.compilation
    else:
        compilation = Compilation()
        for _, tree in _parse_sources(_pyslang(), paths, parse_options=parse_options,
                                      compilation_unit=compilation_unit, proxy_context=python_context):
            compilation.addSyntaxTree(tree)
        compilation = compile_source_trees(compilation.getSyntaxTrees())
    source_ids = {_source_class_id(symbol): symbol for symbol in facts}
    collected: dict[str, dict] = {}
    explicit = {item["canonical_id"]: item for item in existing}
    foreign = {item["canonical_id"]: item for item in python_context}
    visiting: set[str] = set()

    def specialization_id(symbol, source):
        def token(value):
            return "".join(character if character.isascii() and character.isalnum()
                           else f"_x{ord(character):x}_" for character in value)

        arguments = []
        for member in source:
            if member.kind.name == "TypeParameter":
                arguments.append("type_" + token(_canonical_sv_handle_type(member.targetType.type)))
            elif member.kind.name == "Parameter" and not member.isLocalParam:
                arguments.append("value_" + token(str(member.type)) + "_" + token(str(member.value)))
        return _source_class_id(symbol) + "/specialization/" + "/".join(arguments)

    def collect(class_id: str, *, actual_source=None, source_symbol=None):
        if value_exports is None:
            return collect_bound(class_id, actual_source=actual_source, source_symbol=source_symbol)
        symbol = source_symbol or source_ids.get(class_id, _source_class_selector(class_id))
        instance = _instance_scope(symbol)
        scope = None
        if instance is not None:
            from .source_scopes import lookup_native_scope, native_scope_chain
            native = lookup_native_scope(compilation, instance[0])
            body = native_scope_chain(compilation, instance[0])[0]
            scope = {'kind': 'instance', 'path': instance[0], 'container': body.definition.definitionKind.name.lower()}
            value_exports.register_instance(getattr(native, 'body', native), scope)
        with value_exports.instance_context(scope):
            return collect_bound(class_id, actual_source=actual_source, source_symbol=source_symbol)

    def collect_bound(class_id: str, *, actual_source=None, source_symbol=None):
        if class_id in explicit:
            return explicit[class_id]
        if class_id in collected:
            return collected[class_id]
        if class_id in visiting:
            raise SVXInheritanceError(f"cyclic SV source discovery at {class_id}")
        symbol = source_symbol or source_ids.get(class_id, _source_class_selector(class_id))
        fact = facts.get(symbol)
        if fact is None:
            raise SVXInheritanceError(f"SV mirror base {class_id!r} was not found in scanned sources")
        if fact.python_proxy_id is not None:
            parent = foreign.get(fact.python_proxy_id)
            if parent is None:
                raise SVXInheritanceError(
                    f"SV Proxy {symbol} refers to undiscovered Python class {fact.python_proxy_id}"
                )
            expected_base = fact.direct_base
            if expected_base is None:
                raise SVXInheritanceError(f"SV Proxy {symbol} has no declared SV base")
            if "::" not in expected_base:
                expected_base = symbol.split("::")[0] + "::" + expected_base
            expected_id = "sv://" + expected_base.replace("::", "/")
            visiting.add(class_id)
            collect(expected_id)
            visiting.remove(class_id)
            direct_ids = parent.get("mirror_base_ids", [])
            lineage = parent.get("base_lineage", [])
            if direct_ids and expected_id not in direct_ids:
                raise SVXInheritanceError(f"SV Proxy {symbol} base does not match Python Mirror base")
            if lineage and lineage[-1].get("canonical_id") != expected_id:
                raise SVXInheritanceError(f"SV Proxy {symbol} base does not match Python lineage")
            return parent
        visiting.add(class_id)
        package_name = symbol.split('::')[0]
        source = actual_source or _lookup_sv_symbol(compilation, symbol)
        if source is not None and source.isClass:
            source = source.canonicalType
        if source is None or not hasattr(source, "constructor"):
            raise SVXInheritanceError(f"cannot resolve SV class {symbol} in supplied sources")
        specialization = None
        if fact.parameter_kinds:
            arguments = []
            for member in source:
                if member.kind.name == "TypeParameter":
                    actual_type = member.targetType.type
                    argument_binding = binding(actual_type, where=f"{symbol} parameter {member.name}")
                    if actual_type.canonicalType.isClass or actual_type.canonicalType.isVirtualInterface:
                        # A type parameter instantiates the original native SV
                        # class; its RemoteRef codec is only the transport ABI.
                        argument_binding['sv'] = _canonical_sv_handle_type(actual_type)
                    arguments.append({"kind": "type", "type": argument_binding})
                elif member.kind.name == "Parameter" and not member.isLocalParam:
                    if member.type.isIntegral and not member.value.hasUnknown():
                        value = int(member.value.value)
                    elif member.type.isString:
                        value = str(member.value.value)
                    else:
                        raise SVXInheritanceError(
                            f"SV source discovery {symbol} parameter {member.name} "
                            "requires explicit closed specialization metadata")
                    arguments.append({"kind": "value", "sv_type": str(member.type), "value": value})
            if tuple(argument["kind"] for argument in arguments) != fact.parameter_kinds:
                raise SVXInheritanceError(
                    f"SV source discovery {symbol} has no closed default specialization")
            specialization = {"arguments": arguments}
        base_id = None
        if fact.direct_base:
            parent_symbol = fact.direct_base
            if "::" not in parent_symbol:
                lexical = symbol.rsplit('::', 1)[0] + '::' + parent_symbol
                parent_symbol = lexical if lexical in facts else f"{package_name}::{parent_symbol}"
            parent_id = _source_class_id(parent_symbol)
            parent_actual = None
            if (parent_id not in explicit and source.baseClass is not None
                    and parent_symbol in facts and facts[parent_symbol].python_proxy_id is None):
                parent_source = _lookup_sv_symbol(compilation, parent_symbol)
                if parent_source is None or not source.baseClass.isMatching(parent_source.canonicalType):
                    parent_actual = source.baseClass
                    parent_id = specialization_id(parent_symbol, parent_actual)
            parent = collect(parent_id, actual_source=parent_actual, source_symbol=parent_symbol)
            base_id = parent["canonical_id"]

        def parameters(member, location):
            directions = {"In": "input", "Out": "output", "InOut": "inout", "Ref": "ref"}
            result = []
            for argument in member.arguments:
                direction = directions[argument.direction.name]
                if direction == "ref":
                    raise SVXInheritanceError(f"{location}.{argument.name} uses unsupported ref")
                result.append({"name": argument.name, "direction": direction,
                               **value_type(argument.type, f"{location}.{argument.name}")})
            return result

        def value_type(actual, location):
            result = {"type": binding(actual, where=location)}
            handle = _source_handle_metadata(actual, where=location, collections=True)
            if handle is not None:
                if _instance_scope(symbol) is not None:
                    raise SVXInheritanceError(f'{location}: instance-owned handle adapters remain unfinished')
                result["handle"] = handle
            return result

        methods = []
        for method in fact.methods:
            if not selected_member(symbol, method.name):
                continue
            member = source.lookupName(method.name)
            if member is None or not hasattr(member, "arguments"):
                raise SVXInheritanceError(f"cannot resolve SV signature {symbol}.{method.name}")
            if member.visibility.name == "Local":
                continue
            result_type = ({"type": "void"} if method.kind == "task" or str(member.returnType) == "void"
                           else value_type(member.returnType, f"{symbol}.{method.name} return"))
            entry = {"canonical_id": f"{class_id}#{method.name}",
                            "name": method.name, "parameters": parameters(member, f"{symbol}.{method.name}"),
                            "return_type": result_type["type"], "timing": method.kind,
                            "virtual": member.isVirtual,
                            "static": bool(member.flags & MethodFlags.Static),
                            "pure_virtual": bool(member.flags & MethodFlags.Pure)}
            if "handle" in result_type:
                entry["return_handle"] = result_type["handle"]
            methods.append(entry)
        fields = []
        for field in fact.fields:
            if not selected_member(symbol, field.name):
                continue
            member = source.lookupName(field.name)
            if member is None or not hasattr(member, "type"):
                raise SVXInheritanceError(f"cannot resolve SV field {symbol}.{field.name}")
            if member.visibility.name == "Local":
                continue
            if "static" in field.qualifiers:
                raise SVXInheritanceError(f"cannot automatically export static SV field {symbol}.{field.name}; exclude it with --exclude-member")
            fields.append({"name": field.name, **value_type(member.type, f"{symbol}.{field.name}")})
        declaration = {"canonical_id": class_id, "language": "sv", "symbol": symbol,
                       "constructor": {"initiator": "sv", "parameters": (
                           parameters(source.constructor, f"{symbol}.new")
                           if source.constructor is not None else [])},
                       "methods": methods, "fields": fields, "base_lineage": [],
                       "discovery_base_id": base_id}
        unit = _unit_scope(symbol)
        if unit is not None:
            declaration['symbol'] = '$unit::' + unit[1]
            declaration['source_scope'] = {'kind': 'compilation_unit', 'index': unit[0]}
        instance = _instance_scope(symbol)
        if instance is not None:
            declaration['symbol'] = instance[1]
            declaration['source_scope'] = instance_analysis.scopes[symbol]
        if specialization is not None:
            declaration["specialization"] = specialization
        visiting.remove(class_id)
        collected[class_id] = declaration
        return declaration

    for class_id in class_ids:
        collect(class_id)
    exposed = [(_declaration_source_symbol(item), member['name']) for item in collected.values()
               for member in (*item['methods'], *item['fields'])]
    for pattern in member_patterns:
        if not any(fnmatchcase(name, pattern) or fnmatchcase(symbol + '.' + name, pattern)
                   or fnmatchcase(_source_display_name(symbol) + '.' + name, pattern)
                   for symbol, name in exposed):
            raise SVXInheritanceError(f'SV member selector {pattern!r} matched no accessible member in selected classes or their ancestors')
    return list(collected.values())


@with_instance_discovery
def validate_sv_declarations(
    declarations: Iterable[dict[str, object]], paths: Iterable[Path], *, parse_options=None,
    compilation_unit=False, proxy_context=()
) -> None:
    """Require SV manifest declarations to agree with parsed source facts."""

    declarations = tuple(
        item
        for declaration in declarations
        for item in (declaration, *declaration.get("base_lineage", []))
        if item.get("language", "sv") == "sv"
    )
    paths = tuple(paths)
    if any((declaration.get('source_scope') or {}).get('kind') == 'instance' for declaration in declarations):
        from .sv_instance_scan import prepare_instance_analysis
        patterns = [(item['source_scope']['path'] + '.' + item['symbol']) for item in declarations
                    if (item.get('source_scope') or {}).get('kind') == 'instance']
        prepare_instance_analysis(paths, parse_options=parse_options, compilation_unit=compilation_unit, patterns=patterns)
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=proxy_context)
    for declaration in declarations:
        symbol = declaration.get("symbol")
        if not isinstance(symbol, str):
            continue
        fact = facts.get(_declaration_source_symbol(declaration))
        if fact is None:
            raise SVXInheritanceError(
                f"SV declaration {symbol} was not found in scanned sources"
            )
        source_lineage = _source_lineage(fact, facts)
        specialization = declaration.get("specialization")
        if isinstance(specialization, dict):
            arguments = specialization.get("arguments", [])
            if not isinstance(arguments, list) or len(arguments) != len(fact.parameter_kinds):
                raise SVXInheritanceError(
                    f"SV declaration {symbol} specialization requires "
                    f"{len(fact.parameter_kinds)} ordered source parameters"
                )
            for index, (argument, expected_kind) in enumerate(zip(arguments, fact.parameter_kinds)):
                actual_kind = argument.get("kind") if isinstance(argument, dict) else None
                if actual_kind != expected_kind:
                    raise SVXInheritanceError(
                        f"SV declaration {symbol} specialization argument {index} "
                        f"expects {expected_kind}, got {actual_kind}"
                    )
        lineage = declaration.get("base_lineage", [])
        if isinstance(lineage, list) and lineage:
            direct_parent = lineage[-1]
            if isinstance(direct_parent, dict) and direct_parent.get("language") == "sv":
                parent_symbol = direct_parent.get("symbol")
                if isinstance(parent_symbol, str):
                    expected = parent_symbol.rsplit("::", 1)[-1]
                    if fact.direct_base not in {expected, parent_symbol, _declaration_source_symbol(direct_parent)}:
                        raise SVXInheritanceError(
                            f"SV declaration {symbol} expects direct base {expected}, "
                            f"but source extends {fact.direct_base or '<none>'}"
                        )
        for method in declaration.get("methods", []):
            if not isinstance(method, dict):
                continue
            name = method.get("name")
            if method.get("virtual", False) and not any(
                name in ancestor.virtual_methods for ancestor in source_lineage
            ):
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} is virtual in the manifest "
                    "but not in source"
                )
            declaring_fact = next((ancestor for ancestor in source_lineage
                                   if any(item.name == name for item in ancestor.methods)), None)
            if method.get("static", False) and (
                declaring_fact is None or name not in declaring_fact.static_methods
            ):
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} is static in the manifest "
                    "but not in source"
                )
            source_method = next((item for ancestor in source_lineage for item in ancestor.methods
                                  if item.name == name), None)
            if source_method is None:
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} was not found in scanned source lineage"
                )
            if "timing" in method and method["timing"] != source_method.kind:
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} timing is {method['timing']}, "
                    f"but source is {source_method.kind}"
                )
            if "parameters" not in method:
                continue
            parameters = method["parameters"]
            if not isinstance(parameters, list) or len(parameters) != len(source_method.parameters):
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} requires "
                    f"{len(source_method.parameters)} ordered source parameters"
                )
            for index, (parameter, source_parameter) in enumerate(zip(parameters, source_method.parameters)):
                if (not isinstance(parameter, dict)
                    or parameter.get("name") != source_parameter.name
                    or parameter.get("direction", "input") != source_parameter.direction):
                    raise SVXInheritanceError(
                        f"SV declaration {symbol}.{name} parameter {index} expects "
                        f"{source_parameter.direction} {source_parameter.name}"
                    )
    _validate_member_types(declarations, paths, facts, parse_options=parse_options,
                           compilation_unit=compilation_unit, proxy_context=proxy_context)


def _declared_sv_type(value: object, handle: object = None) -> str | None:
    if (isinstance(value, dict) and isinstance(value.get('svtypes'), dict)
            and value['svtypes'].get('kind') == 'collection' and isinstance(handle, dict)):
        return value.get('sv')
    if isinstance(handle, dict) and isinstance(handle.get("sv_type"), str):
        return handle["sv_type"]
    if isinstance(value, dict) and isinstance(value.get("sv"), str):
        return value["sv"]
    return "void" if value == "void" else None


def _declared_class_reference(declaration) -> str:
    from .inheritance import _sv_specialization_value
    reference = declaration["symbol"]
    if _unit_scope(_declaration_source_symbol(declaration)) is not None:
        reference = reference.removeprefix('$unit::')
    specialization = declaration.get("specialization")
    if isinstance(specialization, dict):
        arguments = [(_declared_sv_type(argument.get("type")) if argument["kind"] == "type"
                      else _sv_specialization_value(argument["value"]))
                     for argument in specialization["arguments"]]
        if any(argument is None for argument in arguments):
            raise SVXInheritanceError(f"SV declaration {reference} lacks a closed specialization type")
        reference += "#(" + ", ".join(arguments) + ")"
    return reference


def _canonical_sv_handle_type(actual) -> str:
    actual = actual.canonicalType
    if actual.isVirtualInterface:
        return "virtual " + str(actual)
    spelling = str(actual)
    selector = _semantic_class_selector(actual) if actual.isClass else actual.lexicalPath
    unit = _unit_scope(selector)
    instance = _instance_scope(selector)
    native = '$unit::' + unit[1] if unit is not None else instance[1] if instance is not None else selector
    return (native + spelling[len(actual.name):]
            if spelling.startswith(actual.name) else spelling)


def _source_handle_metadata(actual, *, where, collections=False):
    original = actual
    actual = actual.canonicalType
    if collections and actual.kind.name in {'QueueType', 'DynamicArrayType',
                                             'FixedSizeUnpackedArrayType', 'AssociativeArrayType'}:
        return _source_handle_metadata(actual.elementType, where=where, collections=True)
    if actual.isClass:
        if actual.genericClass is not None:
            if original.kind.name == "TypeAlias":
                selector = _semantic_class_selector(original)
                unit = _unit_scope(selector)
                return {"kind": "sv_class", "sv_type": '$unit::' + unit[1] if unit is not None else selector,
                        "target_type_name": _source_class_id(selector)}
            raise SVXInheritanceError(f"{where} requires explicit closed class-handle target metadata")
        return {"kind": "sv_class", "sv_type": _canonical_sv_handle_type(actual),
                "target_type_name": _source_class_id(_semantic_class_selector(actual))}
    if actual.isVirtualInterface:
        interface = actual.iface.body.definition.name
        modport = actual.modport.name if actual.modport is not None else "full"
        expected = interface + ("." + modport if modport != "full" else "")
        if str(actual) != expected:
            raise SVXInheritanceError(f"{where} requires explicit closed virtual-interface metadata")
        return {"kind": "virtual_interface", "sv_type": "virtual " + expected,
                "target_type_name": f"sv-vif://{interface}/{modport}"}
    return None


def normalize_sv_handle_types(declarations, paths, *, parse_options=None, compilation_unit=False,
                               proxy_context=()) -> None:
    """Canonicalize all resolvable endpoint types together, not field by field."""
    from pyslang.ast import Compilation

    syntax = _pyslang()
    declarations = tuple(declarations)
    def member_handles(member):
        if not isinstance(member, dict):
            return
        for item in (member, *member.get('parameters', [])):
            handle = item.get('handle')
            if isinstance(handle, dict):
                yield handle
                for operation in handle.get('operations', []):
                    yield from member_handles(operation.get('method'))
        if isinstance(member.get('return_handle'), dict):
            yield member['return_handle']

    def declared_handles(declaration):
        for base in declaration.get('base_lineage', []):
            yield from declared_handles(base)
        for member in (*declaration.get('fields', []), declaration.get('constructor'), *declaration.get('methods', [])):
            yield from member_handles(member)

    if not any(True for declaration in declarations for _ in declared_handles(declaration)):
        return
    proxy_context = tuple(proxy_context) or _python_proxy_context(declarations)
    compilation = Compilation()
    manager = analysis_source_manager()
    occupied = set()
    paths = tuple(paths)
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=proxy_context)
    source_units = {}
    for unit_index, (path, tree) in enumerate(_parse_sources(syntax, paths, manager, parse_options=parse_options,
                                     compilation_unit=compilation_unit, proxy_context=proxy_context)):
        source_units[unit_index] = paths if compilation_unit and unit_index == 0 else (path,)
        compilation.addSyntaxTree(tree)
        for node in (tree.root, *getattr(tree.root, "members", ())):
            name = str(getattr(getattr(node, "header", None), "name", "")).strip()
            if name:
                occupied.add(name)

    probes = []
    unit_probes = {}
    def visit(declaration):
        for base in declaration.get("base_lineage", []):
            visit(base)
        handles = [handle for member in (*declaration.get("fields", []),
                                          declaration.get("constructor"), *declaration.get("methods", []))
                   for handle in member_handles(member)]
        if not handles:
            return
        package = "svx_handle_type_probe"
        while package in occupied:
            package += "_"
        occupied.add(package)
        symbol = declaration.get("symbol")
        source_known = declaration.get("language") == "sv" and _declaration_source_symbol(declaration) in facts
        unit = _unit_scope(_declaration_source_symbol(declaration)) if source_known else None
        lines = [] if unit is not None else [f"package {package};"]
        if source_known and unit is None:
            lines.append(f"import {symbol.split('::')[0]}::*;")
        extends = " extends " + _declared_class_reference(declaration) if source_known else ""
        probe_name = package if unit is not None else 'Probe'
        lines.append(f"virtual class {probe_name}{extends};")
        for index, handle in enumerate(handles):
            lines.extend([f"function void check_{index}(input {handle['sv_type']} value);", "endfunction"])
        lines.append('endclass')
        if unit is not None:
            unit_probes.setdefault(unit[0], []).append('\n'.join(lines))
            probes.append((f'$unit[{unit[0]}]::{probe_name}', handles))
            return
        lines.append('endpackage')
        tree = syntax.SyntaxTree.fromText("\n".join(lines) + "\n", manager,
                                          **({} if parse_options is None else {"options": parse_options}))
        if tree.diagnostics:
            raise SVXInheritanceError(f"invalid SV handle type expression in {symbol}")
        compilation.addSyntaxTree(tree)
        probes.append((package + '::Probe', handles))
    for declaration in declarations:
        visit(declaration)
    compilation = _compile_owner_probes(compilation, unit_probes, manager, parse_options, source_units, proxy_context)
    updates = []
    targets = {}
    for package, handles in probes:
        probe = _lookup_sv_symbol(compilation, package)
        for index, handle in enumerate(handles):
            actual = probe.lookupName(f"check_{index}").arguments[0].type.canonicalType
            if actual.isError:
                # Interface-only source inputs may deliberately omit an opaque
                # external class definition. Keep its explicit contract; this
                # is not evidence of source type validation for that class.
                continue
            expected_kind = "virtual_interface" if actual.isVirtualInterface else "sv_class" if actual.isClass else None
            if handle.get("kind") != expected_kind:
                raise SVXInheritanceError(f"SV handle type {handle['sv_type']} does not match kind {handle.get('kind')}")
            target = handle.get("target_type_name")
            previous = targets.setdefault(target, actual)
            if not previous.isMatching(actual):
                raise SVXInheritanceError(
                    f"one foreign handle target must have one static SV type: {target!r} "
                    f"is declared as both {_canonical_sv_handle_type(previous)!r} "
                    f"and {_canonical_sv_handle_type(actual)!r}"
                )
            updates.append((handle, _canonical_sv_handle_type(actual)))
    for handle, spelling in updates:
        handle["sv_type"] = spelling


def resolve_sv_field_handles(declarations, paths, *, parse_options=None, compilation_unit=False,
                              proxy_context=()) -> dict[tuple[int, str], dict[str, str]]:
    """Resolve native handle leaves, including collection fields and aliases."""
    from pyslang.ast import Compilation

    syntax = _pyslang()
    declarations = tuple(declarations)
    paths = tuple(paths)
    proxy_context = tuple(proxy_context) or _python_proxy_context(declarations)
    compilation = Compilation()
    manager = analysis_source_manager()
    occupied = set()
    source_units = {}
    for unit_index, (path, tree) in enumerate(_parse_sources(syntax, paths, manager, parse_options=parse_options,
                                     compilation_unit=compilation_unit, proxy_context=proxy_context)):
        source_units[unit_index] = paths if compilation_unit and unit_index == 0 else (path,)
        compilation.addSyntaxTree(tree)
        for node in (tree.root, *getattr(tree.root, "members", ())):
            name = str(getattr(getattr(node, "header", None), "name", "")).strip()
            if name:
                occupied.add(name)
    probes = []
    unit_probes = {}
    for declaration in declarations:
        symbol = declaration["symbol"]
        reference = _declared_class_reference(declaration)
        package = "svx_field_type_probe"
        while package in occupied:
            package += "_"
        occupied.add(package)
        unit = _unit_scope(_declaration_source_symbol(declaration))
        probe_name = package if unit is not None else 'Probe'
        lines = ([f'virtual class {probe_name} extends {reference};'] if unit is not None else
                 [f"package {package};", f"import {symbol.split('::')[0]}::*;",
                  f"virtual class Probe extends {reference};"])
        for index, field in enumerate(declaration.get("fields", [])):
            handle = field.get("handle")
            if isinstance(handle, dict):
                lines.extend([f"function void check_{index}(input {handle['sv_type']} value);", "endfunction"])
        lines.append('endclass')
        if unit is not None:
            unit_probes.setdefault(unit[0], []).append('\n'.join(lines))
            probes.append((declaration, f'$unit[{unit[0]}]::{probe_name}'))
            continue
        lines.append('endpackage')
        tree = syntax.SyntaxTree.fromText("\n".join(lines) + "\n", manager,
                                          **({} if parse_options is None else {"options": parse_options}))
        if tree.diagnostics:
            raise SVXInheritanceError(f"SV declaration {symbol} has an invalid field handle type expression")
        compilation.addSyntaxTree(tree)
        probes.append((declaration, package + '::Probe'))
    compilation = _compile_owner_probes(compilation, unit_probes, manager, parse_options, source_units, proxy_context)
    result = {}
    for declaration, package in probes:
        probe = _lookup_sv_symbol(compilation, package)
        source = probe.baseClass
        for index, field in enumerate(declaration.get("fields", [])):
            name = field["name"]
            where = f"SV field {declaration['symbol']}.{name}"
            member = source.lookupName(name) if source is not None else None
            if member is None or not hasattr(member, "type"):
                raise SVXInheritanceError(f"{where} was not declared in source")
            actual = member.type.canonicalType
            if actual.isError:
                raise SVXInheritanceError(f"cannot resolve {where} type; supply its type dependencies")
            element = actual
            while element.isArray:
                element = element.arrayElementType.canonicalType
            if actual.isArray and (element.isClass or element.isVirtualInterface):
                from .inheritance import _type_binding, _handle_binding
                raw_type = field.get('type')
                handle = field.get('handle')
                if (isinstance(handle, dict) and isinstance(raw_type, dict)
                        and ('svtypes' in raw_type or 'python' in raw_type)):
                    binding = _type_binding(raw_type, where, allow_void=False)
                    if _handle_binding(handle, binding, where).collection_binding is None:
                        raise SVXInheritanceError(f'{where} handle metadata disagrees with its source container type')
                actual = element
            if not actual.isClass and not actual.isVirtualInterface:
                if field.get("handle") is not None:
                    raise SVXInheritanceError(f"{where} handle metadata disagrees with its source type")
                continue
            if member.visibility.name == "Local" or member.lifetime.name == "Static":
                raise SVXInheritanceError(f"{where} is not an accessible instance handle")
            existing = field.get("handle")
            if isinstance(existing, dict):
                expected = probe.lookupName(f"check_{index}").arguments[0].type
                if expected.isError or not actual.isMatching(expected):
                    raise SVXInheritanceError(f"{where} handle metadata disagrees with its source type")
            sv_type = _canonical_sv_handle_type(actual)
            kind = "virtual_interface" if actual.isVirtualInterface else "sv_class"
            result[(id(declaration), name)] = {"kind": kind, "sv_type": sv_type}
    return result


def _validate_member_types(declarations, paths, facts, *, parse_options=None, compilation_unit=False,
                           proxy_context=()) -> None:
    """Compare language types without inferring or replacing SvTypes codecs."""

    scope_probes = {}
    from pyslang.ast import Compilation, MethodFlags
    from .inheritance import (
        _sv_specialization_value, _type_binding, _sv_collection_typedef,
        _handle_binding, _handle_adapter_name, _sv_native_handle_collection_typedefs,
    )

    syntax = _pyslang()
    compilation = Compilation()
    source_manager = analysis_source_manager()
    occupied = {symbol.split("::")[0] for symbol in facts}
    paths = tuple(paths)
    source_units = {}
    for unit_index, (path, tree) in enumerate(_parse_sources(syntax, paths, source_manager, parse_options=parse_options,
                                     compilation_unit=compilation_unit, proxy_context=proxy_context)):
        source_units[unit_index] = paths if compilation_unit and unit_index == 0 else (path,)
        compilation.addSyntaxTree(tree)
        for node in (tree.root, *getattr(tree.root, "members", ())):
            name = str(getattr(getattr(node, "header", None), "name", "")).strip()
            if name:
                occupied.add(name)
    probes = []
    unit_probes = {}
    for declaration in declarations:
        symbol = declaration.get("symbol")
        if not isinstance(symbol, str):
            continue
        checks = []
        value_typedefs = {}

        def expected_type(raw_binding, handle):
            expected = _declared_sv_type(raw_binding, handle)
            if (isinstance(raw_binding, dict) and isinstance(handle, dict)
                    and ("svtypes" in raw_binding or "python" in raw_binding)):
                binding = _type_binding(raw_binding, f"SV declaration {symbol} signature", allow_void=False)
                native = _handle_binding(handle, binding, f"SV declaration {symbol} handle")
                if native.collection_binding is not None and _sv_collection_typedef(binding) is not None:
                    aliases, root = _sv_native_handle_collection_typedefs(
                        native, _handle_adapter_name(native) + '_native')
                    value_typedefs.update(aliases)
                    return root
            if (isinstance(raw_binding, dict) and handle is None
                    and ("svtypes" in raw_binding or "python" in raw_binding)):
                binding = _type_binding(raw_binding, f"SV declaration {symbol} signature", allow_void=False)
                alias = _sv_collection_typedef(binding)
                if alias is not None:
                    value_typedefs[alias[0]] = alias[1]
                    return alias[0]
            return expected

        for method in declaration.get("methods", []):
            if not isinstance(method, dict):
                continue
            for index, parameter in enumerate(method.get("parameters", [])):
                expected = expected_type(parameter.get("type"), parameter.get("handle"))
                if expected is not None:
                    checks.append(("method", method["name"], index, expected,
                                   "parameter " + parameter["name"]))
            expected = expected_type(method.get("return_type"), method.get("return_handle"))
            if expected is not None:
                checks.append(("method", method["name"], None, expected, "return type"))
        constructor = declaration.get("constructor")
        if isinstance(constructor, dict):
            for index, parameter in enumerate(constructor.get("parameters", [])):
                expected = expected_type(parameter.get("type"), parameter.get("handle"))
                if expected is not None:
                    checks.append(("constructor", "new", index, expected,
                                   "parameter " + parameter["name"]))
        for field in declaration.get("fields", []):
            expected = expected_type(field.get("type"), field.get("handle"))
            if expected is not None:
                checks.append(("field", field["name"], 0, expected, "field type"))
        methods = declaration.get("methods", [])
        if not checks and not methods and not isinstance(constructor, dict):
            continue
        reference = symbol.removeprefix('$unit::') if _unit_scope(_declaration_source_symbol(declaration)) is not None else symbol
        specialization = declaration.get("specialization")
        if isinstance(specialization, dict):
            arguments = []
            for argument in specialization["arguments"]:
                if argument["kind"] == "type":
                    expected = _declared_sv_type(argument.get("type"))
                    if expected is None:
                        raise SVXInheritanceError(f"SV declaration {symbol} lacks a closed specialization type")
                    arguments.append(expected)
                else:
                    arguments.append(_sv_specialization_value(argument["value"]))
            reference += "#(" + ", ".join(arguments) + ")"
        package = "svx_signature_probe"
        while package in occupied:
            package += "_"
        occupied.add(package)
        unit = _unit_scope(_declaration_source_symbol(declaration))
        instance = _instance_scope(_declaration_source_symbol(declaration))
        container = (declaration.get('source_scope') or {}).get('container', 'module')
        local_instance = False
        if instance is not None:
            from .sv_instance_scan import active_instance_analysis
            from .source_scopes import lookup_native_scope
            analysis = active_instance_analysis(paths, parse_options, compilation_unit)
            native = lookup_native_scope(analysis.compilation, instance[0]) if analysis is not None else None
            local_instance = (analysis is not None
                              and (native.kind.name == 'GenerateBlock'
                                   or container == 'program'
                                   or _has_instance_named_values(declaration, getattr(native, 'body', native))))
        probe_name = package if unit is not None else 'Probe'
        lines = ([f'virtual class Probe extends {reference};'] if local_instance else
                 [f'{container} {package} #(parameter type SVXNativeType);',
                  'virtual class Probe extends SVXNativeType;'] if instance is not None else
                 [f'virtual class {probe_name} extends {reference};'] if unit is not None else
                 [f"package {package};", f"import {symbol.split('::')[0]}::*;",
                  f"virtual class Probe extends {reference};"])
        lines.extend(value_typedefs.values())
        for index, (_, _, argument_index, expected, _) in enumerate(checks):
            signature = (f"function {expected} check_{index}();" if argument_index is None
                         else f"function void check_{index}(input {expected} value);")
            lines.extend((signature, "endfunction"))
        lines.append('endclass')
        if local_instance:
            scope_probes.setdefault(instance[0], []).append({'name': package, 'text': '\n'.join(lines)})
            probes.append((symbol, f'$instance[{instance[0]}.{package}]::Probe', checks, constructor, methods))
            continue
        if unit is not None:
            unit_probes.setdefault(unit[0], []).append('\n'.join(lines))
            probes.append((symbol, f'$unit[{unit[0]}]::{probe_name}', checks, constructor, methods))
            continue
        if instance is not None:
            lines.extend([f'end{container}',
                          f'bind {instance[0]} {package} #(.SVXNativeType({reference})) {package}();'])
        else:
            lines.append('endpackage')
        tree = syntax.SyntaxTree.fromText("\n".join(lines) + "\n", source_manager,
                                          **({} if parse_options is None else {"options": parse_options}))
        if tree.diagnostics:
            raise SVXInheritanceError(f"SV declaration {symbol} has an invalid signature type expression")
        compilation.addSyntaxTree(tree)
        probes.append((symbol, (f'$instance[{instance[0]}.{package}]::Probe' if instance is not None
                                else package + '::Probe'), checks, constructor, methods))
    compilation = _compile_owner_probes(compilation, unit_probes, source_manager, parse_options, source_units,
                                         proxy_context, scope_probes)
    for symbol, package, checks, constructor, methods in probes:
        probe = _lookup_sv_symbol(compilation, package)
        if probe is None:
            raise SVXInheritanceError(f'cannot bind SV signature validation to the original owner of {symbol}')
        source = probe.baseClass
        if source is None:
            raise SVXInheritanceError(f"cannot resolve SV class {symbol} in supplied sources")
        for method in methods:
            name = method['name']
            member = source.lookupName(name)
            if member is None or not hasattr(member, 'arguments'):
                raise SVXInheritanceError(f"cannot resolve SV signature {symbol}.{name} in supplied sources")
            if member.visibility.name == 'Local':
                raise SVXInheritanceError(f"SV declaration {symbol}.{name} cannot expose a local member")
            qualifiers = {
                'virtual': member.isVirtual,
                'static': bool(member.flags & MethodFlags.Static),
                'pure_virtual': bool(member.flags & MethodFlags.Pure),
            }
            for qualifier, actual in qualifiers.items():
                # Partial source-fact consumers can omit virtual; complete
                # manifest methods require it. static/pure default to false.
                if qualifier == 'virtual' and qualifier not in method:
                    continue
                declared = method.get(qualifier, False)
                if declared != actual:
                    raise SVXInheritanceError(
                        f"SV declaration {symbol}.{name} {qualifier} is {declared}, "
                        f"but source is {actual}"
                    )
        if isinstance(constructor, dict):
            arguments = source.constructor.arguments if source.constructor is not None else ()
            parameters = constructor.get("parameters", [])
            if len(parameters) != len(arguments):
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.new requires {len(arguments)} ordered source parameters"
                )
            directions = {"In": "input", "Out": "output", "InOut": "inout", "Ref": "ref"}
            for index, (parameter, argument) in enumerate(zip(parameters, arguments)):
                direction = directions[argument.direction.name]
                if (parameter.get("name") != argument.name
                    or parameter.get("direction", "input") != direction):
                    raise SVXInheritanceError(
                        f"SV declaration {symbol}.new parameter {index} expects {direction} {argument.name}"
                    )
        for index, (kind, name, argument_index, _, location) in enumerate(checks):
            member = source.constructor if kind == "constructor" else source.lookupName(name)
            expected_method = probe.lookupName(f"check_{index}")
            if member is None or not hasattr(member, "type" if kind == "field" else "arguments"):
                raise SVXInheritanceError(f"cannot resolve SV signature {symbol}.{name} in supplied sources")
            if kind == 'field' and member.visibility.name == 'Local':
                raise SVXInheritanceError(f"SV declaration {symbol}.{name} cannot expose a local member")
            actual = (member.type if kind == "field" else member.returnType if argument_index is None
                      else member.arguments[argument_index].type)
            expected = (expected_method.returnType if argument_index is None
                        else expected_method.arguments[0].type)
            if actual.isError or expected.isError:
                raise SVXInheritanceError(
                    f"cannot resolve SV declaration {symbol}.{name} {location} type; "
                    "supply its type dependencies in the scanned sources"
                )
            if not actual.isMatching(expected):
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} {location} {expected} "
                    f"does not match source type {actual}"
                )
