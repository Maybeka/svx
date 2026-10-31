"""Publish scoped classes without inventing or relocating native SV types."""

import ast
import keyword
from pathlib import PurePosixPath

from .errors import SVXInheritanceError
from .source_scopes import instance_public_module, source_class_parts


def _scope_component(part):
    capitals = '_'.join(str(index) for index, character in enumerate(part) if character.isupper()) or 'none'
    return f's{len(part)}_{part}_u{capitals}'


def scoped_public_module(symbol, source_scope=None):
    if source_scope is not None and source_scope['kind'] == 'instance':
        return instance_public_module(source_scope['path'])
    return ('svx_mirror_unit.unit_' + str(source_scope['index']) if source_scope is not None
            else 'svx_mirror.' + symbol.split('::')[0])


def scoped_implementation_module(symbol, source_scope=None):
    if source_scope is not None and source_scope['kind'] == 'instance':
        root = ('_svx_instance_scoped_classes', *instance_public_module(source_scope['path']).split('.')[1:])
    else:
        root = ('_svx_unit_scoped_classes', 'unit_' + str(source_scope['index'])) if source_scope is not None else ('_svx_scoped_classes', symbol.split('::')[0])
    return '.'.join((*root, *map(_scope_component, source_class_parts(symbol, source_scope)), '_definition'))


def scoped_sv_package(symbol, role):
    stem = '_'.join(map(_scope_component, symbol.split('::')))
    return 'svx_scoped_' + role + '_' + stem


def merge_scoped_class_sources(manifest, sources):
    from .inheritance import (_all_manifest_classes, _generated_python_header,
                              _generated_python_init, _python_module_for)
    from .package_exports import _isolate_support_names

    grouped = {}
    for source in _all_manifest_classes(manifest):
        parts = source_class_parts(source.symbol, source.source_scope)
        if source.language != 'sv' or len(parts) <= 1:
            continue
        if any(keyword.iskeyword(part) for part in parts):
            raise SVXInheritanceError(f'scoped class {source.symbol} contains a name incompatible with Python syntax')
        module = _python_module_for(source)
        path = PurePosixPath(*module.split('.')).with_suffix('.py')
        text = sources.get(path)
        if text is None:
            continue
        tree = ast.parse(text)
        if not any(isinstance(node, ast.ClassDef) and node.name == source.name for node in tree.body):
            raise SVXInheritanceError(f'scoped class {source.symbol} needs a separate source layout; integrated layout remains unfinished')
        public_module = scoped_public_module(source.symbol, source.source_scope)
        qualname = '.'.join(parts)
        sources[path] = text.rstrip() + (f'\n\n{source.name}.__module__ = {public_module!r}\n'
                                       f'{source.name}.__qualname__ = {qualname!r}\n')
        for depth in range(1, len(module.split('.'))):
            sources.setdefault(PurePosixPath(*module.split('.')[:depth], '__init__.py'),
                               _generated_python_init(manifest, 'scoped class implementation package'))
        grouped.setdefault(public_module, []).append((parts, module, source.name))
    if not grouped:
        return sources
    for root in sorted({module.split('.')[0] for module in grouped}):
        path = PurePosixPath(root, '__init__.py')
        if path not in sources:
            sources[path] = _generated_python_init(manifest, 'generated SystemVerilog mirror package')
    for public_module, declarations in sorted(grouped.items()):
        path = PurePosixPath(*public_module.split('.')).with_suffix('.py')
        original = sources.get(path)
        if original is None:
            original = '\n'.join(_generated_python_header(manifest, role='scoped class public names'))
            original += '\nfrom __future__ import annotations\n'
        roots = {parts[0] for parts, _, _ in declarations}
        declared = {node.name for node in ast.parse(original).body if isinstance(node, ast.ClassDef)}
        original = _isolate_support_names(original, roots - declared)
        tree = ast.parse(original)
        occupied = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | roots
        occupied.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
        occupied.update(alias.asname or alias.name.split('.')[0]
                        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                        for alias in node.names)
        occupied.update(node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)))

        def private_name(stem):
            while stem in occupied:
                stem += '_'
            occupied.add(stem)
            return stem

        namespace = private_name('_svx_scope_namespace')
        lines = [original.rstrip(), '', f'from types import SimpleNamespace as {namespace}']
        available = {(node.name,) for node in tree.body if isinstance(node, ast.ClassDef)}
        for parts, implementation, name in sorted(declarations, key=lambda item: (len(item[0]), item[0])):
            for index in range(1, len(parts)):
                prefix = tuple(parts[:index])
                if prefix not in available:
                    lines.append('.'.join(prefix) + ' = ' + namespace + '()')
                    available.add(prefix)
            alias = private_name('_svx_scoped_type')
            lines.extend([f'from {implementation} import {name} as {alias}',
                          '.'.join(parts) + ' = ' + alias])
            available.add(tuple(parts))
        sources[path] = '\n'.join(lines).rstrip() + '\n'
    return sources
