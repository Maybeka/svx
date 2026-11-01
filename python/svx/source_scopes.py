"""Readable identities for native instance-bound class declarations."""

import re
import keyword
import json

from .errors import SVXInheritanceError


_INSTANCE_COMPONENT = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)((?:\[-?[0-9]+\])*)')


def instance_path_components(path):
    if not isinstance(path, str) or not path:
        raise SVXInheritanceError('instance source_scope.path must be a nonempty native hierarchy path')
    result = []
    for component in path.split('.'):
        match = _INSTANCE_COMPONENT.fullmatch(component)
        if match is None:
            raise SVXInheritanceError(f'invalid native instance path component {component!r}')
        name, dimensions = match.groups()
        indices = tuple(int(index) for index in re.findall(r'\[(-?[0-9]+)\]', dimensions))
        if dimensions != ''.join(f'[{index}]' for index in indices):
            raise SVXInheritanceError('instance indices must use canonical decimal spelling')
        result.append((name, indices))
    return tuple(result)


def instance_namespace_parts(path):
    """Keep ordinary names and reversibly spell array indices without hashes."""
    result = []
    for name, indices in instance_path_components(path):
        if indices:
            result.append(f'svx_scope_{len(name)}_{name}' + ''.join(
                '_m' + str(-index) if index < 0 else '_p' + str(index) for index in indices))
        elif name == 'classes' or name.startswith('svx_scope_') or keyword.iskeyword(name):
            result.append('svx_scope_id_' + name)
        else:
            result.append(name)
    return tuple(result)


def instance_class_id(path, symbol):
    return 'sv://instance/' + '/'.join((*instance_namespace_parts(path), 'class', *symbol.split('::')))


def instance_public_module(path):
    return '.'.join(('svx_mirror_instance', *instance_namespace_parts(path), 'classes'))


def source_class_parts(symbol, source_scope=None):
    parts = symbol.split('::')
    return parts if source_scope is not None and source_scope['kind'] == 'instance' else parts[1:]


def lookup_native_scope(compilation, path):
    """Resolve actual hierarchy, including implicit genblk names hidden by lookupName."""
    root = compilation.getRoot()

    def active(symbol):
        if symbol is None:
            return False
        if symbol.kind.name == 'Instance':
            return not symbol.body.isUninstantiated
        return symbol.kind.name == 'GenerateBlock' and not symbol.isUninstantiated

    direct = root.lookupName(path)
    if active(direct):
        return direct
    scope = root
    prefix = []
    for component in path.split('.'):
        prefix.append(component)
        symbol = scope.lookupName(component)
        if symbol is None:
            match = _INSTANCE_COMPONENT.fullmatch(component)
            if match is None:
                return None
            name, indices = match.groups()
            symbol = scope.find(name)
            for index in re.findall(r'\[(-?[0-9]+)\]', indices):
                if symbol is None:
                    return None
                if symbol.kind.name == 'GenerateBlockArray':
                    symbol = next((entry for entry in symbol.entries if entry is not None and entry.arrayIndex == int(index)), None)
                elif symbol.kind.name == 'InstanceArray':
                    expected = '.'.join(prefix)
                    symbol = next((entry for entry in symbol.elements if entry.hierarchicalPath == expected
                                   or expected.startswith(entry.hierarchicalPath + '[')), None)
                else:
                    return None
        if not active(symbol):
            return None
        scope = getattr(symbol, 'body', symbol)
    return symbol


def native_scope_chain(compilation, path):
    """Return the real instance body and each lexical generate owner below it."""
    owner = lookup_native_scope(compilation, path)
    if owner is None or owner.kind.name not in {'Instance', 'GenerateBlock'}:
        raise SVXInheritanceError(f'cannot resolve native class owner at {path}')
    if owner.kind.name == 'Instance':
        return (owner.body,)
    body = owner.containingInstance
    parts = path.split('.')
    scopes = [body]
    for size in range(len(body.hierarchicalPath.split('.')) + 1, len(parts) + 1):
        scope = lookup_native_scope(compilation, '.'.join(parts[:size]))
        if scope is None or scope.kind.name != 'GenerateBlock':
            raise SVXInheritanceError(f'cannot resolve lexical generate owner at {path}')
        scopes.append(scope)
    return tuple(scopes)


def selected_native_scopes(compilation, patterns):
    """Visit requested concrete owners, avoiding a full hierarchy for exact paths."""
    exact = set()
    for pattern in patterns:
        path, separator, _ = pattern.rpartition('.')
        plain = re.sub(r'\[-?[0-9]+\]', '', pattern)
        if not separator or any(character in plain for character in '*?['):
            exact.clear()
            break
        exact.add(path)
    if exact:
        for path in sorted(exact):
            scope = lookup_native_scope(compilation, path)
            if scope is not None:
                body = scope.body if scope.kind.name == 'Instance' else scope.containingInstance
                yield getattr(scope, 'body', scope), {
                    'kind': 'instance', 'path': path,
                    'container': body.definition.definitionKind.name.lower()}
        return

    def instances(instance):
        if instance.kind.name == 'InstanceArray':
            for element in instance.elements:
                yield from instances(element)
        else:
            yield from walk(instance.body, instance.body.definition.definitionKind.name.lower())

    def walk(scope, container):
        yield scope, {'kind': 'instance', 'path': scope.hierarchicalPath, 'container': container}
        for member in scope:
            kind = member.kind.name
            if kind in {'Instance', 'InstanceArray'}:
                yield from instances(member)
            elif kind == 'GenerateBlock' and not member.isUninstantiated:
                yield from walk(member, container)
            elif kind == 'GenerateBlockArray':
                for block in member.entries:
                    if block is not None and not block.isUninstantiated:
                        yield from walk(block, container)
    for instance in compilation.getRoot().topInstances:
        yield from instances(instance)


def native_scope_insertions(compilation, entries, *, manager=None, reachable_buffers=None, guarded=True):
    """Anchor local adapters and capture parent guards before lexical children."""
    manager = manager or compilation.sourceManager
    anchored = {}
    generated_names = set()
    lexical_declarations = set()

    def anchor(location, text, name):
        if not manager.isFileLoc(location):
            raise SVXInheritanceError('native owner source integration requires direct anchors; macro-generated owners remain unfinished')
        if reachable_buffers is not None and location.buffer not in reachable_buffers:
            raise SVXInheritanceError('native owner was loaded from a library; source-copy library replacement remains unfinished')
        chunk = ('\n`line 1 ' + json.dumps('svx-generated/' + name + '.sv') + ' 0\n' + text
                 + '\n`line ' + str(manager.getLineNumber(location)) + ' '
                 + json.dumps(str(manager.getFileName(location)), ensure_ascii=False) + ' 0\n')
        anchored.setdefault((location.buffer, location.offset), []).append(chunk)

    def scalar_condition(scope, location):
        conditions = []
        instance = scope.kind.name == 'InstanceBody'
        for parameter in scope:
            if parameter.kind.name == 'TypeParameter' and not parameter.isLocalParam:
                raise SVXInheritanceError('native source placement for owner type parameters remains unfinished')
            if parameter.kind.name != 'Parameter':
                continue
            if instance and parameter.isLocalParam:
                continue
            if not instance and str(getattr(parameter.syntax, 'kind', '')) != 'SyntaxKind.IdentifierName':
                continue  # Only the implicit genvar parameter can vary independently here.
            if not (parameter.type.isIntegral or parameter.type.isString or parameter.type.isFloating):
                raise SVXInheritanceError('native source placement for structured owner parameters remains unfinished')
            if not manager.isBeforeInCompilationUnit(parameter.location, location):
                raise SVXInheritanceError(f'owner parameter {parameter.name} needs late-declaration guard placement; this layout remains unfinished')
            operator = '===' if parameter.type.isIntegral else '=='
            conditions.append(f'({parameter.name} {operator} {parameter.value})')
        return ' && '.join(conditions) or '1'

    for path, items in entries.items():
        scopes = native_scope_chain(compilation, path)
        for entry in items:
            identity = (path, entry['name'])
            if identity in generated_names:
                raise SVXInheritanceError(f'duplicate generated local bridge name at {path}: {entry["name"]}')
            generated_names.add(identity)
            if scopes[-1].lookupName(entry['name']) is not None:
                raise SVXInheritanceError(f'generated local bridge name collides with original design at {path}')
            if entry.get('lexical_declaration'):
                leaf = scopes[-1]
                node = leaf.definition.syntax if leaf.kind.name == 'InstanceBody' else leaf.syntax
                token = getattr(node, 'endmodule' if leaf.kind.name == 'InstanceBody' else 'end', None)
                if token is None or token.isMissing:
                    raise SVXInheritanceError('lexical adapter declarations require a native scope ending')
                declaration = (token.location.buffer, token.location.offset, entry['name'], entry['text'])
                if declaration in lexical_declarations:
                    continue
                lexical_declarations.add(declaration)
                anchor(token.location, entry['text'], entry['name'])
                continue
            previous = None
            if guarded:
                for depth, (parent, child) in enumerate(zip(scopes, scopes[1:])):
                    node = child.syntax
                    parent_syntax = parent.definition.syntax if parent.kind.name == 'InstanceBody' else parent.syntax
                    while node.parent is not parent_syntax and str(getattr(node.parent, 'kind', '')) != 'SyntaxKind.GenerateRegion':
                        node = node.parent
                        if node is None:
                            raise SVXInheritanceError(f'cannot anchor parent scope guard for {path}')
                    location = node.sourceRange.start
                    condition = scalar_condition(parent, location)
                    if previous is not None:
                        condition = f'{previous} && ({condition})'
                    previous = entry['name'] + f'_scope_{depth}'
                    if parent.lookupName(previous) is not None:
                        raise SVXInheritanceError(f'generated scope guard collides with original design at {path}')
                    anchor(location, f'localparam bit {previous} = {condition};', previous)
            leaf = scopes[-1]
            node = leaf.definition.syntax if leaf.kind.name == 'InstanceBody' else leaf.syntax
            token = getattr(node, 'endmodule' if leaf.kind.name == 'InstanceBody' else 'end', None)
            if token is None or token.isMissing:
                raise SVXInheritanceError('single-item generate needs source wrapping; this layout remains unfinished')
            location = token.location
            condition = scalar_condition(leaf, location) if guarded else '1'
            if previous is not None:
                condition = f'{previous} && ({condition})'
            anchor(location, f'if ({condition}) begin : {entry["name"]}\n' + entry['text']
                   + f'\nend : {entry["name"]}', entry['name'])
    result = {}
    for (buffer, offset), chunks in anchored.items():
        result.setdefault(buffer, []).append((offset, '\n'.join(chunks)))
    return result
