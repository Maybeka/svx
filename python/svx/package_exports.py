"""Package callable endpoints on the existing static SvTypes call transport."""

from dataclasses import dataclass
import ast
import builtins
import keyword
from pathlib import PurePosixPath
import symtable
from typing import TYPE_CHECKING

from .errors import SVXInheritanceError

if TYPE_CHECKING:
    from .inheritance import Method


@dataclass(frozen=True)
class PackageCallable:
    symbol: str
    method: 'Method'

    @property
    def package(self):
        return self.symbol.split('::')[0]

    @property
    def name(self):
        return self.symbol.split('::')[1]

    @property
    def owner_id(self):
        return 'svpkg://' + self.package


def parse_package_callables(items):
    from .inheritance import _identifier, _parse_method

    if not isinstance(items, list):
        raise SVXInheritanceError('root.callables must be a list')
    result, seen = [], set()
    for index, item in enumerate(items):
        where = f'root.callables[{index}]'
        if not isinstance(item, dict) or set(item) != {'symbol', 'method'}:
            raise SVXInheritanceError(f'{where} requires symbol and method')
        symbol = item['symbol']
        if not isinstance(symbol, str) or len(symbol.split('::')) != 2:
            raise SVXInheritanceError(f'{where} requires a qualified package callable symbol')
        package, name = symbol.split('::')
        _identifier(package, where + '.package')
        _identifier(name, where + '.name')
        if symbol in seen:
            raise SVXInheritanceError(f'duplicate package callable {symbol}')
        seen.add(symbol)
        method = _parse_method(item['method'], 'svpkg://' + package, where + '.method')
        for name_part in (package, name, *(parameter.name for parameter in method.parameters)):
            if keyword.iskeyword(name_part):
                raise SVXInheritanceError(f'{where} contains a name incompatible with Python syntax: {name_part!r}')
        if method.name != name or not method.is_static or method.virtual or method.pure_virtual:
            raise SVXInheritanceError(f'{where} must describe a nonvirtual static endpoint for {symbol}')
        result.append(PackageCallable(symbol, method))
    return tuple(result)


def callable_owners(manifest):
    """Group transport methods, without adding fictitious class export targets."""
    from .inheritance import ForeignClass

    groups = {}
    for item in manifest.callables:
        groups.setdefault(item.package, []).append(item.method)
    return tuple(ForeignClass('svpkg://' + package, 'sv', package, tuple(methods), None)
                 for package, methods in sorted(groups.items()))


def _isolate_support_names(source, exported_names):
    """Rename generated global helpers without touching public formals or strings."""
    exported_names = set(exported_names)
    tree = ast.parse(source)
    root = symtable.symtable(source, '<svx-generated>', 'exec')
    imports = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == '__future__':
                continue
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias
    collisions = set(exported_names) & (set(imports) | set(dir(builtins)))
    if not collisions:
        return source
    occupied = set(root.get_identifiers()) | set(exported_names)
    occupied.update(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))
    occupied.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    occupied.update(alias.asname or alias.name.split('.')[0]
                    for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names)
    requested = {name: '_svx_package_support_' + name for name in sorted(collisions)}
    renames = {}
    for name, candidate in requested.items():
        while candidate in occupied:
            candidate += '_'
        occupied.add(candidate)
        renames[name] = candidate
    raw = source.encode('utf-8')
    lines = raw.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []

    def replace(node, text):
        edits.append((offsets[node.lineno - 1] + node.col_offset,
                      offsets[node.end_lineno - 1] + node.end_col_offset, text.encode('utf-8')))

    class Rewrite(ast.NodeVisitor):
        table = root
        used_children = {}

        def child_table(self, node, name):
            children = [child for child in self.table.get_children()
                        if child.get_name() == name and child.get_lineno() == node.lineno]
            key = (self.table.get_id(), name, node.lineno)
            index = self.used_children.get(key, 0)
            self.used_children[key] = index + 1
            return children[index]

        def global_name(self, name):
            try:
                return self.table.lookup(name).is_global()
            except KeyError:
                return False

        def visit_Name(self, node):
            if node.id in renames and self.global_name(node.id):
                replace(node, renames[node.id])

        def visit_Import(self, node):
            self.visit_ImportFrom(node)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                local = alias.asname or alias.name.split('.')[0]
                if local in renames and self.global_name(local):
                    replace(alias, alias.name + ' as ' + renames[local])

        def body(self, node, name):
            previous = self.table
            self.table = self.child_table(node, name)
            for child in node.body:
                self.visit(child)
            self.table = previous

        def visit_FunctionDef(self, node):
            for value in (*node.decorator_list, *node.args.defaults,
                          *(item for item in node.args.kw_defaults if item is not None)):
                self.visit(value)
            if node.returns is not None:
                self.visit(node.returns)
            self.body(node, node.name)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            for value in (*node.decorator_list, *node.bases, *node.keywords):
                self.visit(value)
            self.body(node, node.name)

        def visit_Lambda(self, node):
            for value in (*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)):
                self.visit(value)
            previous = self.table
            self.table = self.child_table(node, 'lambda')
            self.visit(node.body)
            self.table = previous

    Rewrite().visit(tree)
    builtin_imports = [f'from builtins import {name} as {renames[name]}'
                       for name in sorted(collisions - set(imports))]
    if builtin_imports:
        future = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == '__future__']
        insertion = offsets[future[-1].end_lineno] if future else 0
        edits.append((insertion, insertion, ('\n' + '\n'.join(builtin_imports) + '\n').encode('utf-8')))
    for start, end, text in sorted(edits, key=lambda item: (item[0], item[1]), reverse=True):
        raw = raw[:start] + text + raw[end:]
    return raw.decode('utf-8')


def merge_callable_sources(manifest, sources):
    from .inheritance import (_generated_python_header, _generated_python_init,
                              _register_contract_lines, _request_values_repr, _sv_generated_names)

    if not manifest.callables:
        return sources
    occupied = {item.name for item in (*manifest.classes, *manifest.value_types,
                                      *manifest.constants, *manifest.callables)}
    occupied.update(parameter.name for item in manifest.callables for parameter in item.method.parameters)
    names = _sv_generated_names(occupied, ('_svx_register_package_contract', '_svx_invoke_package'))
    register, invoke = names['_svx_register_package_contract'], names['_svx_invoke_package']
    for owner in callable_owners(manifest):
        path = PurePosixPath('svx_mirror', owner.symbol + '.py')
        original = sources.get(path)
        if original is None:
            original = '\n'.join(_generated_python_header(manifest, role='public SV package callables'))
            original += '\nfrom __future__ import annotations\n'
        else:
            original = _isolate_support_names(original, (method.name for method in owner.methods))
        lines = [original.rstrip(), '',
                 f'from svx.inheritance import register_contract as {register}',
                 f'from svx.inheritance import invoke_sv_static as {invoke}', '',
                 *_register_contract_lines(owner.methods, function_name=register)]
        for method in owner.methods:
            signature = ', '.join(parameter.name for parameter in method.parameters)
            lines.extend(['', f'def {method.name}({signature}):',
                f'    """Call native {owner.symbol}::{method.name} ({method.timing})."""',
                f'    return {invoke}({owner.canonical_id!r}, {method.canonical_id!r}, {_request_values_repr(method)})'])
        sources[path] = '\n'.join(lines).rstrip() + '\n'
    sources.setdefault(PurePosixPath('svx_mirror/__init__.py'),
                       _generated_python_init(manifest, 'generated SV package exports'))
    return sources


def emit_sv_package_callables(manifest, *, has_records, has_handles):
    from .inheritance import _emit_sv_static_gateway, _sv_value_package_imports

    lines = []
    for owner in callable_owners(manifest):
        package = f'svx_package_calls_{len(owner.symbol)}_{owner.symbol}'
        lines.extend(['', '// Package functions and tasks; original declarations remain unchanged.',
                      f'package {package};', '  import svx_pkg::*;', '  import svtypes_pkg::*;',
                      *_sv_value_package_imports((owner,))])
        if has_records:
            lines.append('  import svx_call_records_pkg::*;')
        if has_handles:
            lines.append('  import svx_external_handles_pkg::*;')
        lines.extend(_emit_sv_static_gateway(owner, gateway_name='PackageGateway',
            dispatcher_name='PackageDispatcher', instance_name='package_dispatcher', inherit_source=False))
        lines.append(f'endpackage : {package}')
    return lines
