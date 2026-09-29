"""SystemVerilog source facts used to validate inheritance declarations.

This module deliberately does not infer SvTypes codecs from SV spelling. SVX
uses SvTypes declarations as its only call-data contract; the source scanner
only establishes language facts that must agree with that contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import SVXInheritanceError


@dataclass(frozen=True)
class SVClassFact:
    """The source-level facts relevant to one SystemVerilog class."""

    symbol: str
    direct_base: str | None
    virtual_methods: frozenset[str]
    static_methods: frozenset[str]


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
    prototype = getattr(declaration, "prototype", None)
    name = getattr(prototype, "name", None)
    if name is None:
        return None
    result = str(name).strip()
    return result if result and result != "new" else None


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


def scan_sv_sources(paths: Iterable[Path]) -> dict[str, SVClassFact]:
    """Parse SV package classes with pyslang and return inheritance facts.

    Each input must contain package-scoped class declarations. Full project
    compilation-unit construction is intentionally left to a later build-file
    frontend; this scanner never substitutes a regex approximation.
    """

    syntax = _pyslang()
    facts: dict[str, SVClassFact] = {}
    for path in paths:
        tree = syntax.SyntaxTree.fromFile(str(path))
        if tree.diagnostics:
            raise SVXInheritanceError(
                f"cannot parse SystemVerilog source {path}: {tree.diagnostics[0]}"
            )
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
                if member.__class__.__name__ != "ClassDeclarationSyntax":
                    continue
                name = str(member.name).strip()
                symbol = f"{package_name}::{name}"
                extends = getattr(member, "extendsClause", None)
                direct_base = (
                    str(getattr(extends, "baseName", "")).strip()
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
                    symbol, direct_base, virtual_methods, static_methods
                )
        if not package_count:
            raise SVXInheritanceError(
                f"SystemVerilog source {path} must contain a package declaration"
            )
    return facts


def scan_sv_virtual_interfaces(paths: Iterable[Path]) -> dict[str, SVVirtualInterfaceFact]:
    """Parse interface declarations and their declared modports with pyslang.

    An interface may live at compilation-unit scope, so its VIF spelling is
    its source name (for example ``bus_if.master``), unlike a package class
    whose spelling is ``pkg::Class``. Generated VIF adapters use this fact to
    reject an unknown modport before generated SV is compiled.
    """

    syntax = _pyslang()
    facts: dict[str, SVVirtualInterfaceFact] = {}
    for path in paths:
        tree = syntax.SyntaxTree.fromFile(str(path))
        if tree.diagnostics:
            raise SVXInheritanceError(
                f"cannot parse SystemVerilog source {path}: {tree.diagnostics[0]}"
            )
        for member in getattr(tree.root, "members", ()):
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
                                    declarator_name, "signal", sv_type
                                )
                            )
                    continue
                if item.__class__.__name__ == "FunctionDeclarationSyntax":
                    prototype = getattr(item, "prototype", None)
                    member_name = str(getattr(prototype, "name", "")).strip()
                    kind = str(getattr(item, "kind", ""))
                    if not member_name:
                        continue
                    is_task = kind == "SyntaxKind.TaskDeclaration"
                    parameters: list[SVInterfaceParameterFact] = []
                    port_list = getattr(prototype, "portList", None)
                    for port in getattr(port_list, "ports", ()):
                        declarator = getattr(port, "declarator", None)
                        parameter_name = str(getattr(declarator, "name", "")).strip()
                        if not parameter_name:
                            continue
                        parameters.append(
                            SVInterfaceParameterFact(
                                parameter_name,
                                str(getattr(port, "direction", "input")).strip() or "input",
                                str(getattr(port, "dataType", "")).strip(),
                            )
                        )
                    members.append(
                        SVInterfaceMemberFact(
                            member_name,
                            "task" if is_task else "function",
                            None if is_task else str(getattr(prototype, "returnType", "")).strip(),
                            tuple(parameters),
                        )
                    )
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


def validate_sv_declarations(
    declarations: Iterable[dict[str, object]], paths: Iterable[Path]
) -> None:
    """Require SV manifest declarations to agree with parsed source facts."""

    facts = scan_sv_sources(paths)
    for declaration in declarations:
        symbol = declaration.get("symbol")
        if not isinstance(symbol, str):
            continue
        fact = facts.get(symbol)
        if fact is None:
            raise SVXInheritanceError(
                f"SV declaration {symbol} was not found in scanned sources"
            )
        lineage = declaration.get("base_lineage", [])
        if isinstance(lineage, list) and lineage:
            direct_parent = lineage[-1]
            if isinstance(direct_parent, dict) and direct_parent.get("language") == "sv":
                parent_symbol = direct_parent.get("symbol")
                if isinstance(parent_symbol, str):
                    expected = parent_symbol.rsplit("::", 1)[-1]
                    if fact.direct_base != expected:
                        raise SVXInheritanceError(
                            f"SV declaration {symbol} expects direct base {expected}, "
                            f"but source extends {fact.direct_base or '<none>'}"
                        )
        for method in declaration.get("methods", []):
            if not isinstance(method, dict):
                continue
            name = method.get("name")
            if method.get("virtual", False) and name not in fact.virtual_methods:
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} is virtual in the manifest "
                    "but not in source"
                )
            if method.get("static", False) and name not in fact.static_methods:
                raise SVXInheritanceError(
                    f"SV declaration {symbol}.{name} is static in the manifest "
                    "but not in source"
                )
