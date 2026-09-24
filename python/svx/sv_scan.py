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
