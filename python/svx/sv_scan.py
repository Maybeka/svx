"""SystemVerilog source facts used to validate inheritance declarations.

This module deliberately does not infer SvTypes codecs from SV spelling. SVX
uses SvTypes declarations as its only call-data contract; the source scanner
only establishes language facts that must agree with that contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

from .errors import SVXInheritanceError


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
    result = str(name).strip()
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
    from pyslang import SourceManager
    paths = tuple(paths)
    if not paths:
        return
    source_manager = source_manager or SourceManager()
    trees = []
    if compilation_unit:
        options = {} if parse_options is None else {"options": parse_options}
        tree = syntax.SyntaxTree.fromFiles([str(path) for path in paths],
                                          source_manager or SourceManager(), **options)
        _check_source_diagnostics(tree, paths[0])
        trees.append((paths[0], tree))
    else:
        for path in paths:
            tree = _parse_source(syntax, path, source_manager, parse_options=parse_options)
            trees.append((path, tree))
    from .sv_library_search import load_libraries
    for path, tree in load_libraries(trees, paths, source_manager, parse_options, compilation_unit):
        yield path, _with_python_proxy_members(tree, proxy_context) if proxy_context else tree


def _is_virtual(item: object) -> bool:
    return any(
        str(qualifier).strip() == "virtual"
        for qualifier in getattr(item, "qualifiers", ())
    )


def _is_static(item: object) -> bool:
    return any(
        str(qualifier).strip() == "static"
        for qualifier in getattr(item, "qualifiers", ())
    )


def _declarator_type(sv_type: str, declarator: object) -> str:
    dimensions = "".join(str(item).strip() for item in getattr(declarator, "dimensions", ()))
    return sv_type + (" " + dimensions if dimensions else "")


def _method_fact(item: object, *, include_constructor: bool = False) -> SVInterfaceMemberFact | None:
    declaration = getattr(item, "declaration", item)
    prototype = getattr(declaration, "prototype", None)
    name = str(getattr(prototype, "name", "")).strip()
    if not name or (name == "new" and not include_constructor):
        return None
    is_task = str(getattr(prototype, "keyword", "")).strip() == "task"
    parameters: list[SVInterfaceParameterFact] = []
    direction = "input"
    sv_type = "logic"
    for port in getattr(getattr(prototype, "portList", None), "ports", ()):
        parameter_name = str(getattr(getattr(port, "declarator", None), "name", "")).strip()
        if not parameter_name:
            continue
        # A new explicit direction starts a new type group (default logic).
        # Only an omitted direction carries the preceding type forward.
        explicit_direction = str(getattr(port, "direction", None) or "").strip()
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
            direction = str(getattr(header, "direction", None) or "input").strip()
            sv_type = str(getattr(header, "dataType", None) or "logic").strip()
            for declarator in getattr(port, "declarators", ()):
                parameter_name = str(getattr(declarator, "name", "")).strip()
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
    return str(identifier if identifier is not None else node).strip()


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


def scan_sv_sources(paths: Iterable[Path], *, allow_no_packages: bool = False, parse_options=None,
                    compilation_unit=False, proxy_context=()) -> dict[str, SVClassFact]:
    """Parse SV package classes with pyslang and return inheritance facts.

    Inputs may be separate parse units or one ordered shared compilation unit.
    Full project libraries / independent unit groups still require a build-file
    frontend; this scanner never substitutes a regex approximation.
    """

    syntax = _pyslang()
    facts: dict[str, SVClassFact] = {}
    trees = tuple(_parse_sources(syntax, paths, parse_options=parse_options,
                                 compilation_unit=compilation_unit, proxy_context=proxy_context))
    aliases = []
    for path, tree in trees:
        roots = [tree.root]
        if not getattr(getattr(tree.root, "header", None), "name", None):
            roots = list(getattr(tree.root, "members", ()))
        package_count = 0
        for root in roots:
            package_name = str(
                getattr(getattr(root, "header", None), "name", "")
            ).strip()
            if not package_name:
                continue
            package_count += 1
            for member in getattr(root, "members", ()):
                if member.__class__.__name__ == "TypedefDeclarationSyntax":
                    aliases.append((package_name, str(member.name).strip()))
                if member.__class__.__name__ != "ClassDeclarationSyntax":
                    continue
                name = str(member.name).strip()
                symbol = f"{package_name}::{name}"
                extends = getattr(member, "extendsClause", None)
                direct_base = (
                    _source_class_name(getattr(extends, "baseName", ""))
                    if extends is not None
                    else None
                )
                virtual_methods = frozenset(
                    name
                    for item in getattr(member, "items", ())
                    if _is_virtual(item) and (name := _method_name(item)) is not None
                )
                static_methods = frozenset(
                    name
                    for item in getattr(member, "items", ())
                    if _is_static(item) and (name := _method_name(item)) is not None
                )
                if symbol in facts:
                    raise SVXInheritanceError(
                        f"duplicate SystemVerilog class definition {symbol}"
                    )
                facts[symbol] = SVClassFact(
                    symbol, direct_base, virtual_methods, static_methods,
                    tuple(
                        "type" if parameter.__class__.__name__ == "TypeParameterDeclarationSyntax"
                        else "value"
                        for parameter in getattr(getattr(member, "parameters", None), "declarations", ())
                        for declarator in getattr(parameter, "declarators", ())
                        if str(getattr(declarator, "name", "")).strip()
                    ),
                    tuple(
                        method for item in getattr(member, "items", ())
                        if (method := _method_fact(item)) is not None
                    ),
                    tuple(
                        SVClassFieldFact(
                            str(declarator.name).strip(),
                            " ".join(str(item.declaration.type).split()),
                            frozenset(str(value).strip() for value in item.qualifiers),
                            bool(getattr(declarator, "dimensions", ())),
                        )
                        for item in getattr(member, "items", ())
                        if item.__class__.__name__ == "ClassPropertyDeclarationSyntax"
                        and item.declaration.__class__.__name__ == "DataDeclarationSyntax"
                        for declarator in item.declaration.declarators
                        if str(getattr(declarator, "name", "")).strip()
                    ),
                    next((
                        method for item in getattr(member, "items", ())
                        if (method := _method_fact(item, include_constructor=True)) is not None
                        and method.name == "new"
                    ), None),
                    _python_proxy_id(member),
                )
        if not package_count and not allow_no_packages:
            raise SVXInheritanceError(
                f"SystemVerilog source {path} must contain a package declaration"
            )
    if aliases:
        from pyslang.ast import Compilation
        compilation = Compilation()
        for _, tree in trees:
            compilation.addSyntaxTree(tree)
        compilation.getRoot()
        for package_name, alias in aliases:
            package = compilation.getPackage(package_name)
            member = package.lookupName(alias) if package is not None else None
            actual = getattr(member, "canonicalType", None)
            if actual is None or not actual.isClass:
                continue
            source = facts.get(actual.lexicalPath)
            if source is not None:
                facts[f"{package_name}::{alias}"] = replace(
                    source, symbol=f"{package_name}::{alias}", parameter_kinds=())
    return facts


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
            name = str(getattr(header, "name", "")).strip()
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
                        declarator_name = str(getattr(declarator, "name", "")).strip()
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
                    modport_name = str(getattr(modport, "name", "")).strip()
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
                        direction = str(
                            getattr(group, "direction", getattr(group, "importExport", ""))
                        ).strip()
                        for port in getattr(group, "ports", ()):
                            port_name = str(getattr(port, "name", "")).strip()
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
) -> list[dict]:
    """Collect requested source ancestors, using the caller's SvTypes bindings.

    Returned classes are discovery context, not generation requests. Explicit
    declarations remain the caller's responsibility and override this context.
    """
    paths = tuple(paths)
    python_context = tuple(python_context)
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=python_context)
    from pyslang.ast import Compilation, MethodFlags

    compilation = Compilation()
    for _, tree in _parse_sources(_pyslang(), paths, parse_options=parse_options,
                                  compilation_unit=compilation_unit, proxy_context=python_context):
        compilation.addSyntaxTree(tree)
    compilation.getRoot()
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
        return "sv://" + symbol.replace("::", "/") + "/specialization/" + "/".join(arguments)

    def collect(class_id: str, *, actual_source=None, source_symbol=None):
        if class_id in explicit:
            return explicit[class_id]
        if class_id in collected:
            return collected[class_id]
        if class_id in visiting:
            raise SVXInheritanceError(f"cyclic SV source discovery at {class_id}")
        symbol = source_symbol or class_id.removeprefix("sv://").replace("/", "::")
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
        package_name, class_name = symbol.split("::")
        package = compilation.getPackage(package_name)
        source = actual_source or (package.lookupName(class_name) if package is not None else None)
        if source is not None and source.isClass:
            source = source.canonicalType
        if source is None or not hasattr(source, "constructor"):
            raise SVXInheritanceError(f"cannot resolve SV class {symbol} in supplied sources")
        specialization = None
        if fact.parameter_kinds:
            arguments = []
            for member in source:
                if member.kind.name == "TypeParameter":
                    arguments.append({"kind": "type", "type": binding(
                        member.targetType.type, where=f"{symbol} parameter {member.name}")})
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
                parent_symbol = f"{package_name}::{parent_symbol}"
            parent_id = "sv://" + parent_symbol.replace("::", "/")
            parent_actual = None
            if (parent_id not in explicit and source.baseClass is not None
                    and parent_symbol in facts and facts[parent_symbol].python_proxy_id is None):
                parent_package_name, parent_name = parent_symbol.split("::")
                parent_package = compilation.getPackage(parent_package_name)
                parent_source = parent_package.lookupName(parent_name) if parent_package is not None else None
                if parent_source is not None and not source.baseClass.isMatching(parent_source.canonicalType):
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
                result["handle"] = handle
            return result

        methods = []
        for method in fact.methods:
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
            member = source.lookupName(field.name)
            if member is None or not hasattr(member, "type"):
                raise SVXInheritanceError(f"cannot resolve SV field {symbol}.{field.name}")
            if member.visibility.name == "Local":
                continue
            if "static" in field.qualifiers:
                raise SVXInheritanceError(f"SV source discovery {symbol}.{field.name} requires explicit static field metadata")
            fields.append({"name": field.name, **value_type(member.type, f"{symbol}.{field.name}")})
        declaration = {"canonical_id": class_id, "language": "sv", "symbol": symbol,
                       "constructor": {"initiator": "sv", "parameters": (
                           parameters(source.constructor, f"{symbol}.new")
                           if source.constructor is not None else [])},
                       "methods": methods, "fields": fields, "base_lineage": [],
                       "discovery_base_id": base_id}
        if specialization is not None:
            declaration["specialization"] = specialization
        visiting.remove(class_id)
        collected[class_id] = declaration
        return declaration

    for class_id in class_ids:
        collect(class_id)
    return list(collected.values())


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
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=proxy_context)
    for declaration in declarations:
        symbol = declaration.get("symbol")
        if not isinstance(symbol, str):
            continue
        fact = facts.get(symbol)
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
                    if fact.direct_base not in {expected, parent_symbol}:
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
    return (actual.lexicalPath + spelling[len(actual.name):]
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
                return {"kind": "sv_class", "sv_type": original.lexicalPath,
                        "target_type_name": "sv://" + original.lexicalPath.replace("::", "/")}
            raise SVXInheritanceError(f"{where} requires explicit closed class-handle target metadata")
        return {"kind": "sv_class", "sv_type": _canonical_sv_handle_type(actual),
                "target_type_name": "sv://" + actual.lexicalPath.replace("::", "/")}
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
    from pyslang import SourceManager
    from pyslang.ast import Compilation

    syntax = _pyslang()
    declarations = tuple(declarations)
    proxy_context = tuple(proxy_context) or _python_proxy_context(declarations)
    compilation = Compilation()
    manager = SourceManager()
    occupied = set()
    paths = tuple(paths)
    facts = scan_sv_sources(paths, allow_no_packages=True, parse_options=parse_options,
                            compilation_unit=compilation_unit, proxy_context=proxy_context)
    for path, tree in _parse_sources(syntax, paths, manager, parse_options=parse_options,
                                     compilation_unit=compilation_unit, proxy_context=proxy_context):
        compilation.addSyntaxTree(tree)
        for node in (tree.root, *getattr(tree.root, "members", ())):
            name = str(getattr(getattr(node, "header", None), "name", "")).strip()
            if name:
                occupied.add(name)

    def member_handles(member):
        if not isinstance(member, dict):
            return
        for item in (member, *member.get("parameters", [])):
            handle = item.get("handle")
            if isinstance(handle, dict):
                yield handle
                for operation in handle.get("operations", []):
                    yield from member_handles(operation.get("method"))
        if isinstance(member.get("return_handle"), dict):
            yield member["return_handle"]

    probes = []
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
        source_known = declaration.get("language") == "sv" and symbol in facts
        lines = [f"package {package};"]
        if source_known:
            lines.append(f"import {symbol.split('::')[0]}::*;")
        extends = " extends " + _declared_class_reference(declaration) if source_known else ""
        lines.append(f"virtual class Probe{extends};")
        for index, handle in enumerate(handles):
            lines.extend([f"function void check_{index}(input {handle['sv_type']} value);", "endfunction"])
        lines.extend(["endclass", "endpackage"])
        tree = syntax.SyntaxTree.fromText("\n".join(lines) + "\n", manager,
                                          **({} if parse_options is None else {"options": parse_options}))
        if tree.diagnostics:
            raise SVXInheritanceError(f"invalid SV handle type expression in {symbol}")
        compilation.addSyntaxTree(tree)
        probes.append((package, handles))
    for declaration in declarations:
        visit(declaration)
    compilation.getRoot()
    updates = []
    targets = {}
    for package, handles in probes:
        probe = compilation.getPackage(package).lookupName("Probe")
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
    from pyslang import SourceManager
    from pyslang.ast import Compilation

    syntax = _pyslang()
    declarations = tuple(declarations)
    proxy_context = tuple(proxy_context) or _python_proxy_context(declarations)
    compilation = Compilation()
    manager = SourceManager()
    occupied = set()
    for path, tree in _parse_sources(syntax, paths, manager, parse_options=parse_options,
                                     compilation_unit=compilation_unit, proxy_context=proxy_context):
        compilation.addSyntaxTree(tree)
        for node in (tree.root, *getattr(tree.root, "members", ())):
            name = str(getattr(getattr(node, "header", None), "name", "")).strip()
            if name:
                occupied.add(name)
    probes = []
    for declaration in declarations:
        symbol = declaration["symbol"]
        reference = _declared_class_reference(declaration)
        package = "svx_field_type_probe"
        while package in occupied:
            package += "_"
        occupied.add(package)
        lines = [f"package {package};", f"import {symbol.split('::')[0]}::*;",
                 f"virtual class Probe extends {reference};"]
        for index, field in enumerate(declaration.get("fields", [])):
            handle = field.get("handle")
            if isinstance(handle, dict):
                lines.extend([f"function void check_{index}(input {handle['sv_type']} value);", "endfunction"])
        lines.extend(["endclass", "endpackage"])
        tree = syntax.SyntaxTree.fromText("\n".join(lines) + "\n", manager,
                                          **({} if parse_options is None else {"options": parse_options}))
        if tree.diagnostics:
            raise SVXInheritanceError(f"SV declaration {symbol} has an invalid field handle type expression")
        compilation.addSyntaxTree(tree)
        probes.append((declaration, package))
    compilation.getRoot()
    result = {}
    for declaration, package in probes:
        probe = compilation.getPackage(package).lookupName("Probe")
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

    from pyslang.ast import Compilation, MethodFlags
    from pyslang import SourceManager
    from .inheritance import (
        _sv_specialization_value, _type_binding, _sv_collection_typedef,
        _handle_binding, _handle_adapter_name, _sv_native_handle_collection_typedefs,
    )

    syntax = _pyslang()
    compilation = Compilation()
    source_manager = SourceManager()
    occupied = {symbol.split("::")[0] for symbol in facts}
    for path, tree in _parse_sources(syntax, paths, source_manager, parse_options=parse_options,
                                     compilation_unit=compilation_unit, proxy_context=proxy_context):
        compilation.addSyntaxTree(tree)
        for node in (tree.root, *getattr(tree.root, "members", ())):
            name = str(getattr(getattr(node, "header", None), "name", "")).strip()
            if name:
                occupied.add(name)
    probes = []
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
        reference = symbol
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
        lines = [f"package {package};", f"import {symbol.split('::')[0]}::*;",
                 f"virtual class Probe extends {reference};"]
        lines.extend(value_typedefs.values())
        for index, (_, _, argument_index, expected, _) in enumerate(checks):
            signature = (f"function {expected} check_{index}();" if argument_index is None
                         else f"function void check_{index}(input {expected} value);")
            lines.extend((signature, "endfunction"))
        lines.extend(("endclass", "endpackage"))
        tree = syntax.SyntaxTree.fromText("\n".join(lines) + "\n", source_manager,
                                          **({} if parse_options is None else {"options": parse_options}))
        if tree.diagnostics:
            raise SVXInheritanceError(f"SV declaration {symbol} has an invalid signature type expression")
        compilation.addSyntaxTree(tree)
        probes.append((symbol, package, checks, constructor, methods))
    compilation.getRoot()
    for symbol, package, checks, constructor, methods in probes:
        probe = compilation.getPackage(package).lookupName("Probe")
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
