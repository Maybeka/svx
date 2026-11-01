"""Public SvTypes value declarations derived from native SV value types."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import importlib
import json
import keyword
from pathlib import PurePosixPath
import sys
from types import ModuleType, SimpleNamespace, new_class

import svtypes

from .errors import SVXInheritanceError

_codegen_values = ContextVar('svx_codegen_value_types', default=False)


def value_key(symbol, scope=None):
    if scope is not None and scope['kind'] == 'instance':
        return '$instance[' + scope['path'] + ']::' + symbol
    return symbol.replace('$unit::', f'$unit[{scope["index"]}]::', 1) if scope is not None else symbol


def native_value_reference(symbol, default_class_owners=()):
    parts = symbol.split('::')
    return '::'.join(part + ('#()' if '::'.join(parts[:index + 1]) in default_class_owners else '')
                     for index, part in enumerate(parts))


def native_value_name(symbol, source_scope=None):
    parts = symbol.split('::')
    if source_scope is not None and source_scope['kind'] == 'instance':
        from .scoped_exports import _scope_component
        return 'SVXInstanceValue_' + '_'.join(map(_scope_component, parts))
    if parts[0] == '$unit':
        from .scoped_exports import _scope_component
        return 'SVXUnitValue_' + '_'.join(map(_scope_component, parts[1:]))
    if len(parts) > 2:
        from .scoped_exports import _scope_component
        return 'SVXScopedValue_' + '_'.join(map(_scope_component, parts))
    package, name = parts
    return f'SVXValue_{len(package)}_{package}_{name}'


def _identifier(value):
    return isinstance(value, str) and value.isascii() and value.isidentifier() and not keyword.iskeyword(value)


@dataclass(frozen=True)
class ValueExport:
    symbol: str
    identity_json: str
    schema_json: str
    source_scope_json: str | None = field(default=None, kw_only=True)
    default_class_owners: tuple[str, ...] = field(default=(), kw_only=True)

    @property
    def native_reference(self):
        return native_value_reference(self.symbol, self.default_class_owners)

    @property
    def source_scope(self):
        return json.loads(self.source_scope_json) if self.source_scope_json else None

    @property
    def key(self):
        return value_key(self.symbol, self.source_scope)

    @property
    def module(self):
        from .scoped_exports import scoped_public_module
        return scoped_public_module(self.symbol, self.source_scope)

    @property
    def name(self):
        return self.symbol.split('::')[-1]

    @property
    def qualname(self):
        from .source_scopes import source_class_parts
        return '.'.join(source_class_parts(self.symbol, self.source_scope))

    def as_dict(self):
        return {'symbol': self.symbol, 'svtypes': json.loads(self.identity_json),
                'schema': json.loads(self.schema_json),
                **({'default_class_owners': list(self.default_class_owners)} if self.default_class_owners else {}),
                **({'source_scope': self.source_scope} if self.source_scope is not None else {})}


@dataclass(frozen=True)
class ConstantExport(ValueExport):
    data_hex: str
    encoding_json: str

    def as_dict(self):
        return {**super().as_dict(), 'data': self.data_hex,
                'encoding_descriptor': json.loads(self.encoding_json)}


def parse_constant_exports(items):
    if not isinstance(items, list):
        raise SVXInheritanceError('root.constants must be a list')
    if any(not isinstance(item, dict) or set(item) - {'source_scope', 'default_class_owners'} != {'symbol', 'svtypes', 'schema', 'data', 'encoding_descriptor'}
           for item in items):
        raise SVXInheritanceError('constant export requires symbol, public SvTypes identity/schema/encoding descriptor and encoded data')
    declarations = parse_value_exports([{key: value for key, value in item.items()
                                         if key not in {'data', 'encoding_descriptor'}}
                                        for item in items])
    result = []
    for declaration, item in zip(declarations, items):
        try:
            if not isinstance(item['data'], str):
                raise ValueError('encoded data must be a hex string')
            data = bytes.fromhex(item['data'])
            if data.hex() != item['data']:
                raise ValueError('encoded data must use canonical lowercase hex')
            codec = svtypes.materialize_type_spec(svtypes.type_spec_from_identity(
                item['svtypes'], location=declaration.symbol), location=declaration.symbol)
            if svtypes.schema_descriptor(codec).to_dict()['schema'] != item['schema']:
                raise ValueError('public SvTypes schema differs from the declared type')
            if svtypes.encoding_descriptor(codec).to_dict() != item['encoding_descriptor']:
                raise ValueError('public SvTypes encoding descriptor differs from the snapshot')
            value, consumed = codec.unpack(data)
            if consumed != len(data) or codec.pack(value) != data:
                raise ValueError('encoded data is not one complete canonical SvTypes value')
        except (TypeError, ValueError, KeyError, AttributeError, ImportError) as error:
            raise SVXInheritanceError(f'invalid constant export {declaration.symbol}: {error}') from error
        result.append(ConstantExport(declaration.symbol, declaration.identity_json,
                                     declaration.schema_json, data.hex(),
                                     json.dumps(item['encoding_descriptor'], sort_keys=True),
                                     source_scope_json=declaration.source_scope_json,
                                     default_class_owners=declaration.default_class_owners))
    return tuple(result)


def parse_value_exports(items):
    if not isinstance(items, list):
        raise SVXInheritanceError('root.value_types must be a list')
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) - {'source_scope', 'default_class_owners'} != {'symbol', 'svtypes', 'schema'}:
            raise SVXInheritanceError('value export requires symbol, public SvTypes identity and schema')
        symbol = item['symbol']
        scope = item.get('source_scope')
        instance = isinstance(scope, dict) and scope.get('kind') == 'instance'
        if instance:
            from .source_scopes import instance_path_components
            if (not {'kind', 'path'} <= set(scope) or set(scope) - {'kind', 'path', 'container'}
                    or not isinstance(scope.get('container', 'module'), str)
                    or scope.get('container', 'module') not in {'module', 'interface', 'program'}):
                raise SVXInheritanceError(f'invalid instance source scope for {symbol!r}')
            instance_path_components(scope['path'])
            scope = {**scope, 'container': scope.get('container', 'module')}
        elif scope is not None and (not isinstance(scope, dict) or set(scope) != {'kind', 'index'}
                or scope['kind'] != 'compilation_unit' or type(scope['index']) is not int or scope['index'] < 0):
            raise SVXInheritanceError(f'invalid compilation-unit source scope for {symbol!r}')
        parts = symbol.split('::') if isinstance(symbol, str) else ()
        if (not isinstance(symbol, str) or len(parts) < (1 if instance else 2)
                or not all(_identifier(part) for part in (parts if instance else parts[1:]))
                or (not instance and (parts[0] != '$unit' if scope is not None else not _identifier(parts[0])))):
            raise SVXInheritanceError(f'value export needs Python-compatible package/type names: {symbol!r}')
        key = value_key(symbol, scope)
        if key in seen:
            raise SVXInheritanceError(f'duplicate value export: {symbol}')
        seen.add(key)
        owners = item.get('default_class_owners', [])
        if (not isinstance(owners, list) or any(not isinstance(owner, str) or
                len(owner.split('::')) < 2 or not symbol.startswith(owner + '::') or
                not all(_identifier(part) for part in owner.split('::')) for owner in owners)
                or len(owners) != len(set(owners))):
            raise SVXInheritanceError(f'invalid default class owners for {symbol!r}')
        if not isinstance(item['svtypes'], dict) or not isinstance(item['schema'], dict):
            raise SVXInheritanceError(f'{symbol} requires public SvTypes identity/schema objects')
        result.append(ValueExport(symbol, json.dumps(item['svtypes'], sort_keys=True),
                                  json.dumps(item['schema'], sort_keys=True),
                                  source_scope_json=json.dumps(scope, sort_keys=True) if scope is not None else None,
                                  default_class_owners=tuple(owners)))
    return tuple(result)


def _schema_annotation(schema, named):
    kind = schema['kind']
    if kind in {'enum', 'struct'}:
        name = schema['type_name']
        if name not in named:
            module, _, symbol = name.rpartition('.')
            if not module or not _identifier(symbol):
                raise SVXInheritanceError(f'invalid public value dependency {name!r}')
            try:
                named[name] = getattr(importlib.import_module(module), symbol)
            except (ImportError, AttributeError) as error:
                raise SVXInheritanceError(f'value type dependency {name!r} must precede its consumer') from error
        return named[name]
    if kind == 'bits':
        name = schema['type_name']
        if name == 'svtypes.Int':
            return svtypes.Int
        if name == 'svtypes.LongInt':
            return svtypes.LongInt
        factory = svtypes.Logic if schema['state_domain'] == '4state' else svtypes.Bit
        shape = tuple(schema['shape']) if schema.get('shape') else schema['width']
        return factory[shape, svtypes.Signed if schema['signed'] else svtypes.Unsigned]
    if kind == 'string':
        return svtypes.String
    if kind == 'remote_ref':
        return svtypes.RemoteRef[schema['target_type_name']]
    if kind == 'real':
        return svtypes.ShortReal if schema['format'] == 'ieee754-binary32' else svtypes.Real
    if kind in {'array', 'dyn_array', 'queue'}:
        element = _schema_annotation(schema['element'], named)
        if kind == 'array':
            return svtypes.Array[element, schema['size']]
        return (svtypes.Queue if kind == 'queue' else svtypes.DynArray)[element]
    if kind == 'assoc_array':
        return svtypes.AssocArray[_schema_annotation(schema['key'], named),
                                  _schema_annotation(schema['value'], named)]
    raise SVXInheritanceError(f'unsupported public SvTypes value schema kind: {kind!r}')


class ValueModules:
    def __init__(self, codegen=False):
        self.saved = {}
        self.named = {}
        self.annotations = {}
        self.codegen = codegen

    def add(self, declaration):
        try:
            return self._add(declaration)
        except SVXInheritanceError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise SVXInheritanceError(f'invalid public SvTypes value declaration {declaration.symbol}: {error}') from error

    def _add(self, declaration):
        data = declaration.as_dict()
        module_name, name = declaration.module, declaration.name
        if module_name not in self.saved:
            previous = sys.modules.get(module_name)
            self.saved[module_name] = previous
            module = ModuleType(module_name)
            sys.modules[module_name] = module
        module = sys.modules[module_name]
        identity, schema = data['svtypes'], data['schema']
        own_name = module_name + '.' + declaration.qualname
        class_name = native_value_name(declaration.symbol, declaration.source_scope) if self.codegen else name
        if schema.get('type_name') == own_name and schema.get('kind') == 'enum':
            members = dict(schema['items'])
            if not all(_identifier(member) for member in members):
                raise SVXInheritanceError(f'{declaration.symbol} has enum members requiring explicit Python aliases')
            collisions = sorted(set(members) & set(dir(svtypes.Enum)))
            if collisions:
                raise SVXInheritanceError(f'{declaration.symbol} has unsupported SvTypes Enum member names: {", ".join(collisions)}')
            base = svtypes.Enum[svtypes.Bit[schema['width'], svtypes.Signed if schema['signed'] else svtypes.Unsigned]]
            annotation = new_class(class_name, (base,), {},
                                   lambda namespace: namespace.update({'__module__': module_name, '__qualname__': declaration.qualname, **members}))
        elif schema.get('type_name') == own_name and schema.get('kind') == 'struct':
            fields = {field['name']: svtypes.materialize_type_spec(
                _schema_annotation(field['type'], self.named), location=declaration.symbol)
                      for field in schema['fields']}
            if not all(_identifier(field) for field in fields):
                raise SVXInheritanceError(f'{declaration.symbol} has fields requiring explicit Python aliases')
            annotation = type(class_name, (svtypes.SvStruct,), {'__module__': module_name, '__qualname__': declaration.qualname, **fields})
        else:
            annotation = _schema_annotation(schema, self.named)
        actual_identity = svtypes.type_spec_identity(annotation)
        actual_schema = svtypes.schema_descriptor(svtypes.materialize_type_spec(
            annotation, location=declaration.symbol)).to_dict()['schema']
        if actual_identity != identity or actual_schema != schema:
            raise SVXInheritanceError(f'{declaration.symbol} differs from its public SvTypes identity/schema')
        owner = module
        for part in declaration.qualname.split('.')[:-1]:
            if not hasattr(owner, part):
                setattr(owner, part, SimpleNamespace())
            owner = getattr(owner, part)
        setattr(owner, name, annotation)
        self.named[schema['type_name']] = annotation
        self.annotations[declaration.key] = annotation
        return annotation

    def close(self):
        for name, previous in reversed(tuple(self.saved.items())):
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


@contextmanager
def value_modules(declarations=(), *, codegen=None):
    codegen = _codegen_values.get() if codegen is None else codegen
    token = _codegen_values.set(codegen)
    modules = ValueModules(codegen)
    try:
        for declaration in declarations:
            modules.add(declaration)
        yield modules
    finally:
        modules.close()
        _codegen_values.reset(token)


def value_implementation_module(module):
    if module.startswith('svx_mirror_instance.'):
        return module.replace('svx_mirror_instance.', '_svx_instance_value_types.', 1)
    return (module.replace('svx_mirror_unit.', '_svx_unit_value_types.', 1) if module.startswith('svx_mirror_unit.')
            else module.replace('svx_mirror.', '_svx_value_types.', 1))


def with_value_types(function=None, *, codegen=None):
    if function is None:
        return lambda target: with_value_types(target, codegen=codegen)
    @wraps(function)
    def wrapped(manifest, *args, **kwargs):
        with value_modules(manifest.value_types, codegen=codegen):
            return function(manifest, *args, **kwargs)
    return wrapped


def merge_value_sources(manifest, sources, header):
    """Prepend ordinary declarations before mirror contract registration."""
    if not manifest.value_types and not manifest.constants:
        return sources
    groups = {}
    for declaration in manifest.value_types:
        groups.setdefault(declaration.module, []).append(declaration)
    for constant in manifest.constants:
        groups.setdefault(constant.module, [])
    all_names = {part for item in (*manifest.value_types, *manifest.constants) for part in item.qualname.split('.')}
    all_names.update(item.name for item in manifest.classes)
    types_name = '_svx_types'
    while types_name in all_names:
        types_name += '_'
    module_name = '_svx_values'
    while module_name in all_names:
        module_name += '_'
    builtins_name = '_svx_builtins'
    while builtins_name in all_names:
        builtins_name += '_'
    codec_name = '_svx_constant_codec'
    while codec_name in all_names:
        codec_name += '_'
    sys_name = '_svx_sys'
    while sys_name in all_names:
        sys_name += '_'
    for module, declarations in groups.items():
        constants = [item for item in manifest.constants if item.module == module]
        lines = [f'import svtypes as {types_name}', f'import sys as {sys_name}',
                 f'{module_name} = {sys_name}.modules[__name__]', '']
        nested = [item for item in (*declarations, *constants) if '.' in item.qualname]
        namespace_name = '_svx_value_namespace'
        while namespace_name in all_names:
            namespace_name += '_'
        if nested:
            lines.append(f'from types import SimpleNamespace as {namespace_name}')
        available = set()
        if any(item.module == module for item in manifest.constants):
            lines.insert(0, f'import builtins as {builtins_name}')
        foreign = {}

        def expression(schema):
            kind = schema['kind']
            if kind in {'enum', 'struct'}:
                full_name = schema['type_name']
                if full_name.startswith('svx_mirror.'):
                    _, package, name = full_name.split('.', 2)
                    owner = 'svx_mirror.' + package
                elif full_name.startswith('svx_mirror_unit.'):
                    _, unit, name = full_name.split('.', 2)
                    owner = 'svx_mirror_unit.' + unit
                elif full_name.startswith('svx_mirror_instance.'):
                    owner, name = full_name.split('.classes.', 1)
                    owner += '.classes'
                else:
                    owner, name = full_name.rsplit('.', 1)
                if owner == module:
                    return module_name + '.' + name
                if owner not in foreign:
                    alias = '_svx_values_' + str(len(foreign))
                    while alias in all_names:
                        alias += '_'
                    foreign[owner] = alias
                return foreign[owner] + '.' + name
            if kind == 'bits':
                type_name = schema['type_name']
                if type_name == 'svtypes.Int':
                    return types_name + '.Int'
                if type_name == 'svtypes.LongInt':
                    return types_name + '.LongInt'
                factory = '.Logic' if schema['state_domain'] == '4state' else '.Bit'
                shape = tuple(schema['shape']) if schema.get('shape') else schema['width']
                return f'{types_name}{factory}[{shape!r}, {types_name}.{"Signed" if schema["signed"] else "Unsigned"}]'
            if kind == 'string':
                return types_name + '.String'
            if kind == 'remote_ref':
                return f'{types_name}.RemoteRef[{schema["target_type_name"]!r}]'
            if kind == 'real':
                return types_name + ('.ShortReal' if schema['format'] == 'ieee754-binary32' else '.Real')
            if kind in {'array', 'dyn_array', 'queue'}:
                factory = {'array': 'Array', 'dyn_array': 'DynArray', 'queue': 'Queue'}[kind]
                suffix = f', {schema["size"]}' if kind == 'array' else ''
                return f'{types_name}.{factory}[{expression(schema["element"])}{suffix}]'
            if kind == 'assoc_array':
                return f'{types_name}.AssocArray[{expression(schema["key"])}, {expression(schema["value"])}]'
            raise SVXInheritanceError(f'cannot render value schema kind {kind!r}')

        def ensure_namespace(name):
            for depth in range(1, len(name.split('.'))):
                prefix = '.'.join(name.split('.')[:depth])
                if prefix not in available:
                    lines.append(f'{prefix} = {namespace_name}()')
                    available.add(prefix)

        for declaration in declarations:
            data = declaration.as_dict()
            schema, name = data['schema'], declaration.qualname
            class_name = native_value_name(declaration.symbol, declaration.source_scope) if '.' in name else name
            ensure_namespace(name)
            lines.append(f'# Native value type: {declaration.symbol}')
            if schema['type_name'] == module + '.' + name and schema['kind'] == 'enum':
                base = f'{types_name}.Bit[{schema["width"]}, {types_name}.{"Signed" if schema["signed"] else "Unsigned"}]'
                lines.append(f'class {class_name}({types_name}.Enum[{base}]):')
                lines.append(f'    __module__ = {module!r}')
                lines.append(f'    __qualname__ = {name!r}')
                lines.extend(f'    {member} = {value}' for member, value in schema['items'])
            elif schema['type_name'] == module + '.' + name and schema['kind'] == 'struct':
                lines.append(f'class {class_name}({types_name}.SvStruct):')
                lines.append(f'    __module__ = {module!r}')
                lines.append(f'    __qualname__ = {name!r}')
                lines.extend(f'    {field["name"]} = {expression(field["type"])}()' for field in schema['fields'])
            else:
                lines.append(f'{name} = {expression(schema)}')
            if '.' in name and schema['type_name'] == module + '.' + name and schema['kind'] in {'enum', 'struct'}:
                lines.append(f'{class_name}.__name__ = {declaration.name!r}')
                lines.append(f'{name} = {class_name}')
            available.add(name)
            lines.append('')
        for constant in constants:
            ensure_namespace(constant.qualname)
            descriptor = json.loads(constant.encoding_json)
            lines.extend([f'# Native compile-time constant: {constant.symbol}',
                f'{codec_name} = {expression(json.loads(constant.schema_json))}()',
                f'if {types_name}.encoding_descriptor({codec_name}).to_dict() != {descriptor!r}:',
                f'    raise {builtins_name}.RuntimeError({("SvTypes encoding changed for " + constant.symbol + "; regenerate SV exports")!r})',
                f'{constant.qualname} = {codec_name}.unpack('
                f'{builtins_name}.bytes.fromhex({constant.data_hex!r}))[0]', ''])
        generated_modules = set(groups)
        imports = [f'import {value_implementation_module(owner) if owner in generated_modules else owner} as {alias}'
                   for owner, alias in foreign.items()]
        lines[3:3] = imports
        helper = value_implementation_module(module)
        sources[PurePosixPath(*helper.split('.')).with_suffix('.py')] = (
            header + 'from __future__ import annotations\n\n' + '\n'.join(lines) + '\n')
        path = PurePosixPath(*module.split('.')).with_suffix('.py')
        original = sources.get(path)
        if original is None:
            original = header + 'from __future__ import annotations\n\n'
        before, marker, after = original.partition('from __future__ import annotations\n')
        if not marker:
            raise SVXInheritanceError(f'generated module {module} lacks its source preamble')
        names = ', '.join(item.name for item in (*declarations, *constants) if '.' not in item.qualname)
        imports = f'from {helper} import {names}\n' if names else ''
        sources[path] = before + marker + '\n' + imports + after
    sources.setdefault(PurePosixPath('svx_mirror/__init__.py'), header)
    sources.setdefault(PurePosixPath('_svx_value_types/__init__.py'), header)
    if any(module.startswith('svx_mirror_unit.') for module in groups):
        sources.setdefault(PurePosixPath('svx_mirror_unit/__init__.py'), header)
        sources.setdefault(PurePosixPath('_svx_unit_value_types/__init__.py'), header)
    for module in groups:
        if module.startswith('svx_mirror_instance.'):
            for name in (module, value_implementation_module(module)):
                parts = name.split('.')
                for depth in range(1, len(parts)):
                    sources.setdefault(PurePosixPath(*parts[:depth], '__init__.py'), header)
    return sources


def publish_scoped_values(manifest, sources):
    """Attach values after class publication, preserving each owner's class object."""
    from .package_exports import _isolate_support_names
    import ast

    grouped = {}
    for item in (*manifest.value_types, *manifest.constants):
        if '.' in item.qualname:
            grouped.setdefault(item.module, []).append(item)
    for module, declarations in grouped.items():
        path = PurePosixPath(*module.split('.')).with_suffix('.py')
        original = sources[path]
        tree = ast.parse(original)
        declared = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        roots = {item.qualname.split('.')[0] for item in declarations}
        original = _isolate_support_names(original, roots - declared)
        occupied = {node.id for node in ast.walk(ast.parse(original)) if isinstance(node, ast.Name)}
        occupied.update(roots)

        def private(stem):
            while stem in occupied:
                stem += '_'
            occupied.add(stem)
            return stem

        helper = private('_svx_scoped_values')
        namespace = private('_svx_value_namespace')
        constant_descriptor = private('_svx_constant_snapshot')
        constant_names = {item.qualname for item in manifest.constants if item.module == module}
        imports = [f'import {value_implementation_module(module)} as {helper}',
                   f'from types import SimpleNamespace as {namespace}']
        if constant_names:
            imports.extend([
                   f'class {constant_descriptor}:',
                   '    def __init__(self, value):',
                   '        self.value = value',
                   '    def __get__(self, instance, owner=None):',
                   '        return self.value'])
        def bindings(selected):
            lines, available = [], set()
            for item in selected:
                parts = item.qualname.split('.')
                for depth in range(1, len(parts)):
                    prefix = '.'.join(parts[:depth])
                    if prefix in available:
                        continue
                    error = 'NameError' if depth == 1 else 'AttributeError'
                    lines.extend(['try:', f'    {prefix}', f'except {error}:',
                                  f'    {prefix} = {namespace}()'])
                    available.add(prefix)
                value = f'{helper}.{item.qualname}'
                if item.qualname in constant_names:
                    owner = '.'.join(parts[:-1])
                    value = f'({constant_descriptor}({value}) if isinstance({owner}, type) else {value})'
                lines.append(f'{item.qualname} = {value}')
            return lines
        # Contracts import public type identities eagerly. Bind before registration,
        # then reattach whenever an actual mirror replaces an owner namespace.
        tree = ast.parse(original)
        insertions = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == '__future__':
                insertions[node.end_lineno] = imports + bindings(declarations)
            elif isinstance(node, ast.ClassDef):
                insertions[node.end_lineno] = bindings(item for item in declarations
                    if item.qualname.startswith(node.name + '.'))
            elif isinstance(node, ast.Assign):
                prefixes = [ast.unparse(target) + '.' for target in node.targets
                            if isinstance(target, (ast.Name, ast.Attribute))]
                insertions[node.end_lineno] = bindings(item for item in declarations
                    if any(item.qualname.startswith(prefix) for prefix in prefixes))
        rendered = []
        for number, line in enumerate(original.splitlines(), 1):
            rendered.append(line)
            if insertions.get(number):
                rendered.extend(['', *insertions[number], ''])
        sources[path] = '\n'.join(rendered) + '\n'
    return sources
