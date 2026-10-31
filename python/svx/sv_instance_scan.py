"""Demand-driven semantic instance discovery within one source operation."""

from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from functools import wraps
from pathlib import Path
import re

from .errors import SVXInheritanceError


_instances = ContextVar('svx_instance_discovery', default=None)


def with_instance_discovery(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if _instances.get() is not None:
            return function(*args, **kwargs)
        token = _instances.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _instances.reset(token)
    return wrapped


def _key(paths, parse_options, compilation_unit):
    from .sv_frontend import source_elaboration_mode
    from .sv_library_search import _search
    return (tuple(str(Path(path).resolve()) for path in paths), id(parse_options),
            compilation_unit, source_elaboration_mode(), id(_search.get()))


def active_instance_analysis(paths, parse_options=None, compilation_unit=False):
    state = _instances.get()
    return state.get(_key(paths, parse_options, compilation_unit)) if state is not None else None


def active_instance_facts(paths, parse_options=None, compilation_unit=False):
    analysis = active_instance_analysis(paths, parse_options, compilation_unit)
    return analysis.facts if analysis is not None else {}


def semantic_instance_selector(actual):
    """Use the actual instance path, never the source definition's lexical path."""
    names = [actual.name]
    node = getattr(getattr(actual, 'syntax', None), 'parent', None)
    while node is not None:
        kind = str(node.kind).removeprefix('SyntaxKind.')
        if kind == 'ClassDeclaration':
            names.insert(0, str(node.name.valueText))
        if kind in {'ModuleDeclaration', 'InterfaceDeclaration', 'ProgramDeclaration', 'GenerateBlock'}:
            break
        node = node.parent
    path = actual.hierarchicalPath
    # The semantic path renders class scopes with :: and closed parameters
    # with #(args); neither belongs to the native instance owner's path.
    marker = re.search(r'\.' + re.escape(names[0]) + r'(?=#\(|::|$)', path)
    if marker is None:
        raise SVXInheritanceError(f'cannot determine concrete native owner of {path}')
    return '$instance[' + path[:marker.start()] + ']::' + '::'.join(names)


@dataclass
class InstanceAnalysis:
    compilation: object
    source_manager: object
    trees: tuple
    options: object
    library_context: object
    facts: dict = field(default_factory=dict)
    actuals: dict = field(default_factory=dict)
    scopes: dict = field(default_factory=dict)


def prepare_instance_analysis(paths, *, parse_options=None, compilation_unit=False, patterns=()):
    from pyslang.ast import Compilation
    from .sv_scan import _parse_sources, _pyslang, _class_fact, _semantic_class_selector
    from .sv_frontend import analysis_source_manager, compile_source_trees, source_elaboration_mode
    from .sv_library_search import _search

    paths = tuple(paths)
    previous = active_instance_analysis(paths, parse_options, compilation_unit)
    if previous is not None:
        return previous
    if source_elaboration_mode() == 'packages':
        raise SVXInheritanceError('instance-owned exports require design hierarchy elaboration; use --sv-elaboration all')
    compilation = Compilation()
    manager = analysis_source_manager()
    trees = tuple(_parse_sources(_pyslang(), paths, manager, parse_options=parse_options,
                                 compilation_unit=compilation_unit))
    for _, tree in trees:
        compilation.addSyntaxTree(tree)
    compilation = compile_source_trees(compilation.getSyntaxTrees())
    result = InstanceAnalysis(compilation, manager, trees, parse_options, _search.get())

    def classes(scope, path, container, prefix=''):
        for member in scope:
            if member.kind.name not in {'ClassType', 'GenericClassDef', 'TypeAlias'}:
                continue
            if getattr(getattr(member, 'visibility', None), 'name', '') in {'Local', 'Protected'}:
                continue
            generic = member.kind.name == 'GenericClassDef'
            resolved = scope.lookupName(member.name) if generic else member
            actual = getattr(resolved, 'canonicalType', None) if resolved is not None else None
            if not generic and (actual is None or not actual.isClass):
                continue
            node = member.syntax if generic else actual.syntax
            if node is None or str(node.kind) != 'SyntaxKind.ClassDeclaration':
                continue
            name = prefix + member.name
            selector = f'$instance[{path}]::{name}'
            result.facts[selector] = _class_fact(selector, node, concrete_alias=member.kind.name == 'TypeAlias')
            result.scopes[selector] = {'kind': 'instance', 'path': path, 'container': container}
            if actual is not None:
                result.actuals[selector] = actual
                classes(actual, path, container, name + '::')

    def walk(scope, path, container):
        classes(scope, path, container)
        for member in scope:
            kind = member.kind.name
            if kind in {'Instance', 'InstanceArray'}:
                walk_instance(member)
            elif kind == 'GenerateBlock' and not member.isUninstantiated:
                walk(member, member.hierarchicalPath, container)
            elif kind == 'GenerateBlockArray':
                for block in member.entries:
                    if block is not None and not block.isUninstantiated:
                        walk(block, block.hierarchicalPath, container)

    def walk_instance(instance):
        if instance.kind.name == 'InstanceArray':
            for element in instance.elements:
                walk_instance(element)
        else:
            walk(instance.body, instance.hierarchicalPath, instance.body.definition.definitionKind.name.lower())

    exact_owners = set()
    for pattern in patterns:
        owner, separator, name = pattern.rpartition('.')
        without_indices = re.sub(r'\[-?[0-9]+\]', '', pattern)
        if not separator or pattern.startswith('sv://') or any(char in without_indices for char in '*?['):
            exact_owners.clear()
            break
        exact_owners.add(owner)
    if exact_owners:
        from .source_scopes import lookup_native_scope
        for path in sorted(exact_owners):
            owner = lookup_native_scope(compilation, path)
            if owner is None:
                continue
            if owner.kind.name == 'Instance':
                classes(owner.body, path, owner.body.definition.definitionKind.name.lower())
            elif owner.kind.name == 'GenerateBlock':
                classes(owner, path, owner.containingInstance.definition.definitionKind.name.lower())
    else:
        for instance in compilation.getRoot().topInstances:
            walk(instance.body, instance.hierarchicalPath, instance.body.definition.definitionKind.name.lower())
    for selector, actual in result.actuals.items():
        fact = result.facts[selector]
        if fact.direct_base is not None:
            declared = actual.parentScope.lookupName(fact.direct_base)
            parent = declared if declared is not None and getattr(declared, 'canonicalType', None) else actual.baseClass
            if parent is not None:
                result.facts[selector] = replace(fact, direct_base=_semantic_class_selector(parent))
    state = _instances.get()
    if state is not None:
        state[_key(paths, parse_options, compilation_unit)] = result
    return result


def needs_instance_analysis(paths, patterns, *, parse_options=None, compilation_unit=False):
    if any(pattern.startswith('sv://instance/') or '.' in pattern for pattern in patterns):
        return True
    if not patterns:
        return False
    from fnmatch import fnmatchcase
    from .sv_inventory import declaration_inventory
    inventory = declaration_inventory(paths, parse_options=parse_options, compilation_unit=compilation_unit,
                                      kinds=('class', 'type'))
    return any(any(scope['kind'] in {'module', 'interface', 'program', 'generate'} for scope in item['scope'])
               and any(fnmatchcase(item['name'], pattern) for pattern in patterns)
               for item in inventory['declarations'])
