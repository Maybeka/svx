"""Read-only declaration inventory, distinct from semantic export qualification."""

from bisect import bisect_right
from fnmatch import fnmatchcase
from pathlib import Path
import re

from .sv_scan import _parse_sources, _pyslang, _token_text


_SCOPES = {
    'PackageDeclaration': 'package',
    'ClassDeclaration': 'class',
    'ModuleDeclaration': 'module',
    'InterfaceDeclaration': 'interface',
    'ProgramDeclaration': 'program',
    'GenerateBlock': 'generate',
}


def _kind(node):
    return str(node.kind).removeprefix('SyntaxKind.')


def _ancestors(node):
    result = []
    parent = node.parent
    while parent is not None:
        result.append(parent)
        parent = parent.parent
    return tuple(reversed(result))


def _location(manager, node, buffers):
    location = manager.getFullyOriginalLoc(node.sourceRange.start)
    if location.buffer not in buffers:
        filename = str(manager.getRawFileName(location.buffer))
        text = manager.getSourceText(location.buffer).encode('utf-8')
        buffers[location.buffer] = (
            str(Path(filename).resolve()) if filename and not filename.startswith('<') else filename,
            [0, *(match.end() for match in re.finditer(b'\n', text))])
    filename, starts = buffers[location.buffer]
    index = bisect_right(starts, location.offset) - 1
    return {'file': filename, 'line': index + 1, 'column': location.offset - starts[index] + 1}


def _scope(node, manager, buffers):
    kind = _SCOPES.get(_kind(node))
    if kind is None:
        return None
    if kind == 'generate':
        label = getattr(node, 'beginName', None) or getattr(node, 'label', None)
        name = _token_text(getattr(label, 'name', ''))
        if not name:
            location = _location(manager, node, buffers)
            name = f'<anonymous@{location["line"]}:{location["column"]}>'
    else:
        name = _token_text(getattr(node, 'name', None)
                           or getattr(getattr(node, 'header', None), 'name', ''))
    return {'kind': kind, 'name': name}


def _symbol(scopes, name):
    if len(scopes) > 1 and scopes[1]['kind'] in {'module', 'interface', 'program'}:
        scopes = scopes[1:]
    result = ''
    previous = None
    for scope in (*scopes, {'kind': 'declaration', 'name': name}):
        separator = '::' if previous in {'package', 'class', 'compilation_unit'} else '.'
        result += (separator if result else '') + scope['name']
        previous = scope['kind']
    return result


def _availability(kind, scopes, ancestors, node):
    visibility = {_token_text(qualifier) for owner in (*ancestors, node)
                  for qualifier in getattr(owner, 'qualifiers', ())}
    if visibility & {'local', 'protected'}:
        return 'not-public', 'Declaration or its enclosing class is local/protected.'
    if any(scope['kind'] in {'module', 'interface', 'program', 'generate'} for scope in scopes):
        owner = next(scope for scope in reversed(scopes) if scope['kind'] in {'module', 'interface', 'program', 'generate'})
        if kind == 'class' and owner['kind'] in {'module', 'interface', 'program', 'generate'}:
            return 'requires-instance', 'Select a concrete elaborated owner path, for example tb.u.Driver; original build top selection is reused and signatures still require validation.'
        if kind == 'type' or kind == 'constant' and not any(scope['kind'] == 'class' for scope in scopes):
            return 'requires-instance', 'Select a concrete owner path for type or compile-time value snapshots; runtime class-field/method use still requires owner-local transport.'
        return 'owner-bridge-pending', 'Export needs an instance/owner-bound bridge; not implemented yet.'
    if scopes[0]['kind'] == 'compilation_unit':
        if kind == 'class':
            return 'selectable', '$unit class export retains lexical nesting, owner-local source copies and an explicit startup module; signatures still require semantic validation.'
        if kind in {'type', 'constant'} and (kind == 'type' or len(scopes) == 1):
            if kind == 'type' and len(scopes) > 1:
                return 'selectable', 'Class-owned $unit type snapshots and same-unit nominal runtime signatures are supported; concrete schemas still require semantic validation.'
            return 'selectable', 'Standalone $unit values and same-unit root nominal runtime types are supported; concrete schemas still require semantic validation.'
        return 'owner-bridge-pending', 'Export needs a bridge in the original compilation unit; not implemented yet.'
    if kind == 'constant' and any(scope['kind'] == 'class' for scope in scopes):
        return 'member-only', 'Standalone selection of class parameters is not implemented.'
    return 'selectable', 'Scope can be selected; concrete types, signatures and visibility still require semantic validation.'


def declaration_inventory(paths, *, parse_options=None, compilation_unit=False,
                          kinds=(), names=()):
    """List active preprocessed declarations without elaborating DUT instances.

    Generate branches are lexical declarations, not proof of instantiated paths.
    Included declarations retain their physical origin and compilation-unit key.
    """
    syntax = _pyslang()
    declarations = []
    dependencies = set()
    units = []
    seen = set()
    for unit_index, (path, tree) in enumerate(_parse_sources(syntax, paths, parse_options=parse_options,
                                                           compilation_unit=compilation_unit)):
        unit = str(Path(path).resolve())
        if unit not in units:
            units.append(unit)
        manager = tree.sourceManager
        locations = {}
        for buffer in manager.getAllBuffers():
            filename = str(manager.getRawFileName(buffer))
            if filename and Path(filename).is_file():
                dependencies.add(str(Path(filename).resolve()))

        def add(node, kind, name):
            if not name:
                return
            ancestors = _ancestors(node)
            # Subroutine-local typedefs/parameters are not externally named APIs.
            if any(_kind(owner) in {'FunctionDeclaration', 'TaskDeclaration', 'FunctionPrototype',
                                    'TaskPrototype'} for owner in ancestors):
                return
            scopes = [scope for owner in ancestors if (scope := _scope(owner, manager, locations))]
            if not scopes or scopes[0]['kind'] != 'package':
                scopes.insert(0, {'kind': 'compilation_unit', 'name': '$unit'})
            if kind == 'package':
                scopes = []
            symbol = _symbol(scopes, name)
            location = _location(manager, node, locations)
            key = (unit, kind, symbol, *location.values())
            if key in seen:
                return
            seen.add(key)
            status, reason = (('selectable', 'Selects owned declarations; imported package APIs are not selected implicitly.')
                              if kind == 'package' else _availability(kind, scopes, ancestors, node))
            item = {'kind': kind, 'symbol': symbol, 'name': name, 'scope': scopes,
                    'compilation_unit': unit, 'location': location,
                    'compilation_unit_index': unit_index,
                    'export_status': status, 'reason': reason}
            if kind == 'package':
                imports = []
                node.visit(lookup_table={syntax.SyntaxKind.PackageImportItem:
                    lambda value: imports.append(_token_text(value.package))})
                item['imports'] = list(dict.fromkeys(imports))
            if (not kinds or kind in kinds) and (not names or any(
                    fnmatchcase(symbol, pattern) or fnmatchcase(name, pattern) for pattern in names)):
                declarations.append(item)

        def visit(node):
            kind = _kind(node)
            if kind in {'PackageDeclaration', 'ClassDeclaration', 'TypedefDeclaration'}:
                add(node, {'PackageDeclaration': 'package', 'ClassDeclaration': 'class',
                           'TypedefDeclaration': 'type'}[kind],
                    _token_text(getattr(node, 'name', None)
                                or getattr(getattr(node, 'header', None), 'name', '')))
            elif kind == 'ParameterDeclaration':
                for declarator in node.declarators:
                    add(node, 'constant', _token_text(getattr(declarator, 'name', '')))
            elif kind in {'FunctionDeclaration', 'TaskDeclaration'}:
                if any(_kind(owner) == 'ClassDeclaration' for owner in _ancestors(node)):
                    return
                add(node, 'callable', _token_text(node.prototype.name))

        tree.root.visit(lookup_table={getattr(syntax.SyntaxKind, name): visit for name in (
            'PackageDeclaration', 'ClassDeclaration', 'TypedefDeclaration',
            'ParameterDeclaration', 'FunctionDeclaration', 'TaskDeclaration')})
    return {'schema_version': 1, 'analysis': 'preprocessed-declarations',
            'elaborated_instances': False, 'compilation_units': units,
            'dependencies': sorted(dependencies),
            'declarations': sorted(declarations,
                key=lambda item: (item['symbol'], item['kind'], item['compilation_unit'],
                                  item['location']['file'], item['location']['line'],
                                  item['location']['column']))}
