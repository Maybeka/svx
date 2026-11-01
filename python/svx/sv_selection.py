"""Explicit export targets, distinct from source parsing dependencies."""

from fnmatch import fnmatchcase
from collections import deque
import re

from .errors import SVXInheritanceError
from .sv_scan import _parse_sources, _pyslang, _unit_scope, _instance_scope, _source_class_id, _source_class_selector


def matches_sv_selector(symbol, pattern, *, relative_units=True):
    """Match the same readable native names for class and value selectors."""
    instance = _instance_scope(symbol)
    if instance is not None:
        if pattern.startswith('sv://instance/'):
            return fnmatchcase(_source_class_id(symbol), pattern)
        full_name = instance[0] + '.' + instance[1]
        literal_indices = re.sub(r'\[(-?[0-9]+|\*|\?)\]', lambda match: '[[]' + match[1] + ']', pattern)
        return fnmatchcase(full_name if '.' in pattern else instance[1] if '::' in pattern else instance[1].rsplit('::', 1)[-1], literal_indices)
    unit = _unit_scope(pattern)
    if unit is not None:
        owner = _unit_scope(symbol)
        return owner is not None and owner[0] == unit[0] and fnmatchcase(owner[1], unit[1])
    owner = _unit_scope(symbol)
    symbol = re.sub(r'^\$unit\[\d+\]', '$unit', symbol)
    return (fnmatchcase(symbol if '::' in pattern else symbol.rsplit('::', 1)[-1], pattern)
            or relative_units and owner is not None and '::' in pattern
            and not pattern.startswith('$unit') and fnmatchcase(owner[1], pattern))


def package_import_names(root):
    """Share immutable import facts only for the same analysis-owned syntax node."""
    from pyslang.syntax import SyntaxKind
    from .sv_frontend import _analysis

    state = _analysis.get()
    cached = state.package_imports.get(id(root)) if state is not None else None
    if cached is not None and cached[0] is root:
        return cached[1]
    imports = []
    root.visit(lookup_table={SyntaxKind.PackageImportItem:
                            lambda item: imports.append(str(item.package.valueText))})
    names = tuple(dict.fromkeys(imports))
    if state is not None:
        state.package_imports[id(root)] = (root, names)
    return names


def source_packages(paths, *, parse_options=None, compilation_unit=False):
    syntax = _pyslang()
    from pyslang.syntax import SyntaxKind

    package_imports = {}
    for _, tree in _parse_sources(syntax, paths, parse_options=parse_options,
                                  compilation_unit=compilation_unit):
        roots = (tree.root,) if tree.root.kind == SyntaxKind.PackageDeclaration else getattr(tree.root, 'members', ())
        for root in roots:
            if root.kind != SyntaxKind.PackageDeclaration:
                continue
            name = str(root.header.name.valueText)
            package_imports[name] = package_import_names(root)
    return package_imports


def select_package_names(package_imports, patterns, recursive=False):
    selected_packages = []
    for pattern in patterns:
        matches = sorted(name for name in package_imports if fnmatchcase(name, pattern))
        if not matches:
            raise SVXInheritanceError(f'SV package selector {pattern!r} matched no package in the supplied build inputs')
        selected_packages.extend(matches)
    pending = deque(dict.fromkeys(selected_packages))
    selected_packages = set()
    while pending:
        name = pending.popleft()
        if name in selected_packages:
            continue
        selected_packages.add(name)
        if recursive:
            for imported in package_imports[name]:
                if imported not in package_imports:
                    raise SVXInheritanceError(f'cannot recursively export {name}: imported package {imported} is absent from supplied build inputs')
                pending.append(imported)
    return selected_packages


def select_sv_classes(paths, facts, *, classes=(), packages=(), recursive=False,
                      exclude=(), parse_options=None, compilation_unit=False, allow_empty=False):
    """Select owned package classes without promoting imported classes implicitly."""
    package_imports = source_packages(paths, parse_options=parse_options, compilation_unit=compilation_unit)
    selected_packages = select_package_names(package_imports, packages, recursive)
    candidates = {symbol for symbol, fact in facts.items()
                  if (symbol.split('::')[0] in package_imports or _unit_scope(symbol) is not None or _instance_scope(symbol) is not None)
                  and fact.python_proxy_id is None}
    selected = {symbol for symbol in candidates if symbol.split('::')[0] in selected_packages}

    for pattern in classes:
        canonical = pattern.startswith('sv://')
        pattern = _source_class_selector(pattern) if canonical and not pattern.startswith('sv://instance/') else pattern
        found = {symbol for symbol in candidates if matches_sv_selector(symbol, pattern, relative_units=not canonical)}
        exact_pattern = re.sub(r'\[-?[0-9]+\]', '', re.sub(r'^\$unit\[\d+\]', '$unit', pattern))
        exact = not any(char in exact_pattern for char in '*?[')
        if exact and len(found) > 1:
            labels = [(_instance_scope(symbol)[0] + '.' + _instance_scope(symbol)[1]
                       if _instance_scope(symbol) is not None else symbol) for symbol in found]
            raise SVXInheritanceError(f'ambiguous SV class {pattern!r}; use a qualified name: ' + ', '.join(sorted(labels)))
        if not found:
            raise SVXInheritanceError(f'SV class selector {pattern!r} matched no package, compilation-unit or instance class in the supplied build inputs')
        selected.update(found)
    selected = {symbol for symbol in selected if not any(
        matches_sv_selector(symbol, pattern) for pattern in exclude)}
    if not selected and not allow_empty:
        raise SVXInheritanceError('SV export selection contains no classes after applying package/class selectors and exclusions')
    return tuple(_source_class_id(symbol) for symbol in sorted(selected))
