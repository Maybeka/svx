"""Discover concrete SV values and describe them through public SvTypes APIs."""

from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from fnmatch import fnmatchcase
import re
from types import new_class

import svtypes

from .errors import SVXInheritanceError
from .value_exports import parse_constant_exports, parse_value_exports, value_modules, _schema_annotation, value_key, native_value_reference


_value_discovery = ContextVar('svx_value_discovery', default=None)


def with_value_discovery(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with value_modules() as modules:
            token = _value_discovery.set(modules)
            try:
                return function(*args, **kwargs)
            finally:
                _value_discovery.reset(token)
    return wrapped


class SourceValues:
    def __init__(self, value_annotations, exclude=(), exclude_constants=(), exclude_callables=()):
        self.modules = _value_discovery.get()
        self.value_annotations = value_annotations
        self.declarations = {}
        self.exclude = tuple(exclude)
        self.constants = {}
        self.exclude_constants = tuple(exclude_constants)
        self.callables = {}
        self.exclude_callables = tuple(exclude_callables)
        self.unit_symbols = {}
        self.unit_indices = {}
        self.instance_symbols = {}
        self.current_instance = None
        self.class_value_symbols = {}
        self.class_value_members = {}
        self.named_value_origins = {}
        self.default_class_owners = set()
        self.class_lookup = None

    def _default_owners(self, symbol):
        return sorted(owner for owner in self.default_class_owners if symbol.startswith(owner + '::'))

    def native_reference(self, actual):
        symbol, _ = self.source_symbol(actual)
        return native_value_reference(symbol, self._default_owners(symbol))

    @staticmethod
    def _generic_value_owner(actual):
        node = getattr(actual, 'syntax', None)
        while node is not None:
            if type(node).__name__ == 'ClassDeclarationSyntax' and node.parameters is not None:
                return True
            node = node.parent
        return False

    def register_class_values(self, native, prefix):
        """Anchor template-owned values to a concrete, usable package class name."""
        key = (native, prefix)
        if key in self.class_value_members:
            return
        members = []
        self.class_value_members[key] = members
        generic = native.genericClass
        if generic is not None and prefix.rsplit('::', 1)[-1] == generic.name:
            default = native.parentScope.lookupName(generic.name)
            if default is None or not getattr(default, 'isClass', False) or not native.isMatching(default.canonicalType):
                return
            self.default_class_owners.add(prefix)
        seen = set()
        def collect(owner, path):
            if owner in seen:
                return
            seen.add(owner)
            for entry in owner:
                member = owner.lookupName(entry.name) if entry.kind.name == 'TransparentMember' else entry
                if member is None or getattr(getattr(member, 'visibility', None), 'name', '') in {'Local', 'Protected'}:
                    continue
                symbol = path + '::' + entry.name
                if member.kind.name == 'ClassType':
                    collect(member, symbol)
                    continue
                if member.kind.name == 'TypeAlias' and member.canonicalType.isClass:
                    collect(member.canonicalType, symbol)
                    continue
                generic = self._generic_value_owner(member)
                if member.kind.name == 'TypeParameter':
                    member = member.typeAlias
                if member.kind.name not in {'TypeAlias', 'Parameter'} or not (generic or self._generic_value_owner(member)):
                    continue
                if member.kind.name == 'TypeAlias' and member.canonicalType.isClass:
                    continue
                self.class_value_symbols.setdefault(member, (symbol, None))
                if member.kind.name == 'TypeAlias':
                    members.append((member, symbol))
                if member.kind.name == 'TypeAlias' and member.canonicalType.lexicalPath == member.lexicalPath:
                    self.class_value_symbols.setdefault(member.canonicalType, (symbol, None))
        collect(native, prefix)

    def publish_class_values(self, native, prefix):
        """Expose each selected class's alias of an already materialized value."""
        self.register_class_values(native, prefix)
        for member, symbol in self.class_value_members[(native, prefix)]:
            if symbol in self.declarations:
                continue
            origin, scope = self.named_value_origins.get(member.canonicalType) or self.source_symbol(member.canonicalType)
            annotation = self.modules.annotations.get(value_key(origin, scope))
            if annotation is not None:
                self._add(symbol, annotation)

    @contextmanager
    def instance_context(self, scope):
        previous = self.current_instance
        self.current_instance = scope
        try:
            yield
        finally:
            self.current_instance = previous

    def register_instance(self, native, scope):
        symbols, types, constants = {}, {}, {}
        self.instance_symbols[scope['path']] = symbols
        def collect(owner, prefix=''):
            for item in owner:
                if getattr(getattr(item, 'visibility', None), 'name', '') in {'Local', 'Protected'}:
                    continue
                if item.kind.name == 'ClassType':
                    symbols[item] = prefix + item.name
                    collect(item, prefix + item.name + '::')
                elif item.kind.name == 'TypeAlias' and item.canonicalType.isClass:
                    symbols[item] = prefix + item.name
                elif item.kind.name == 'TypeAlias' and not item.canonicalType.isClass:
                    symbol = prefix + item.name
                    symbols[item] = symbol
                    if item.canonicalType.lexicalPath == item.lexicalPath:
                        symbols[item.canonicalType] = symbol
                    types[value_key(symbol, scope)] = item
                elif not prefix and item.kind.name == 'Parameter':
                    symbols[item] = item.name
                    constants[value_key(item.name, scope)] = item
        collect(native)
        return types, constants

    def source_symbol(self, actual):
        if self.current_instance is not None:
            symbols = self.instance_symbols.get(self.current_instance['path'], {})
            if actual in symbols:
                return symbols[actual], self.current_instance
        known = self.class_value_symbols.get(actual)
        canonical = getattr(actual, 'canonicalType', None)
        if canonical is not None and canonical.lexicalPath == actual.lexicalPath:
            known = self.class_value_symbols.get(canonical, known)
        if known is None and canonical is not None and self.class_lookup is not None and self._generic_value_owner(actual):
            owner_name, separator, member_name = actual.lexicalPath.rpartition('::')
            owner = self.class_lookup(owner_name) if separator else None
            if owner is not None and getattr(owner, 'isClass', False):
                owner = owner.canonicalType
                member = owner.lookupName(member_name)
                if member is not None and getattr(member, 'canonicalType', None) is not None and member.canonicalType.isMatching(canonical):
                    self.register_class_values(owner, owner_name)
                    known = self.class_value_symbols.get(actual)
                    if canonical.lexicalPath == actual.lexicalPath:
                        known = self.class_value_symbols.get(canonical, known)
        if known is not None:
            return known
        index = self.unit_symbols.get(actual)
        if index is None:
            node = getattr(actual, 'syntax', None)
            generic = False
            while node is not None:
                kind = str(node.kind).removeprefix('SyntaxKind.')
                if kind == 'PackageDeclaration':
                    return actual.lexicalPath, None
                if kind in {'ModuleDeclaration', 'InterfaceDeclaration', 'ProgramDeclaration', 'GenerateBlock'}:
                    raise SVXInheritanceError('instance-owned method/field values need an active owner-bound discovery context; this layout remains unfinished')
                if kind == 'ClassDeclaration' and node.parameters is not None:
                    generic = True
                node = node.parent
            if generic:
                raise SVXInheritanceError('named values from parameterized $unit classes need specialization-aware ownership; this layout remains unfinished')
            parent = getattr(actual, 'parentScope', None)
            if parent is not None and parent.compilationUnit not in self.unit_indices:
                self.unit_indices.update((unit, index) for index, unit in
                                         enumerate(parent.compilation.getRoot().compilationUnits))
            index = self.unit_indices.get(parent.compilationUnit) if parent is not None else None
        if index is not None:
            return '$unit::' + actual.lexicalPath, {'kind': 'compilation_unit', 'index': index}
        return actual.lexicalPath, None

    def callable(self, actual):
        from .declarations import _source_semantic_type_declaration
        from .sv_scan import _source_handle_metadata

        symbol, scope = self.source_symbol(actual)
        owner = 'svpkg://' + symbol.split('::')[0]

        def value_type(native, where):
            result = {'type': _source_semantic_type_declaration(native, where=where,
                value_annotations=self.value_annotations, value_exports=self)}
            handle = _source_handle_metadata(native, where=where, collections=True)
            if handle is not None:
                result['handle'] = handle
            return result

        parameters = []
        for argument in actual.arguments:
            direction = {'In': 'input', 'Out': 'output', 'InOut': 'inout', 'Ref': 'ref'}[argument.direction.name]
            if direction == 'ref':
                raise SVXInheritanceError(f'SV callable {symbol}.{argument.name} uses unsupported ref/const ref')
            parameters.append({'name': argument.name, 'direction': direction,
                               **value_type(argument.type, f'SV callable {symbol}.{argument.name}')})
        timing = actual.subroutineKind.name.lower()
        result = ({'type': 'void'} if timing == 'task' or str(actual.returnType) == 'void'
                  else value_type(actual.returnType, f'SV callable {symbol} return'))
        method = {'canonical_id': owner + '#' + actual.name, 'name': actual.name,
                  'parameters': parameters, 'return_type': result['type'], 'timing': timing,
                  'static': True, 'virtual': False, 'pure_virtual': False}
        if 'handle' in result:
            method['return_handle'] = result['handle']
        self.callables[symbol] = {'symbol': symbol, 'method': method}

    def constant(self, actual, *, symbol=None):
        from .declarations import _source_semantic_type_declaration

        native_symbol, scope = self.source_symbol(actual)
        symbol = symbol or native_symbol
        where = f'SV constant {symbol}'
        binding = _source_semantic_type_declaration(actual.type, where=where,
            value_annotations=self.value_annotations, value_exports=self)
        codec = svtypes.materialize_type_spec(svtypes.type_spec_from_identity(
            binding['svtypes'], location=where), location=where)
        schema = svtypes.schema_descriptor(codec).to_dict()['schema']
        if not actual.value:
            raise SVXInheritanceError(f'{where} has no valid compile-time value')
        try:
            value = self._constant_value(actual.type, actual.value.value, schema)
            data = codec.pack(value)
            declaration, = parse_constant_exports([{'symbol': symbol, 'svtypes': binding['svtypes'],
                'schema': schema, 'encoding_descriptor': svtypes.encoding_descriptor(codec).to_dict(),
                **({'default_class_owners': self._default_owners(symbol)} if self._default_owners(symbol) else {}),
                'data': data.hex(), **({'source_scope': scope} if scope is not None else {})}])
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as error:
            raise SVXInheritanceError(f'{where} cannot be represented by its public SvTypes type: {error}') from error
        self.constants[declaration.key] = declaration

    def _constant_value(self, actual, value, schema):
        actual = actual.canonicalType
        kind = schema['kind']
        if kind in {'bits', 'enum'}:
            if schema['state_domain'] == '4state':
                if not value.hasUnknown:
                    return svtypes.LogicValue(schema['width'], int(value) & ((1 << schema['width']) - 1))
                from pyslang import LiteralBase
                digits = value.toString(LiteralBase.Binary, False)
                return svtypes.LogicValue.from_string(digits.rjust(schema['width'], '0'))
            if value.hasUnknown:
                raise ValueError('X/Z bits cannot be encoded by this two-state SvTypes declaration')
            result = int(value)
            if schema['signed'] and result >= 1 << (schema['width'] - 1):
                result -= 1 << schema['width']
            return result
        if kind in {'string', 'real'}:
            return value
        if kind == 'struct':
            result = svtypes.materialize_type_spec(_schema_annotation(schema, self.modules.named),
                                                   location=actual.lexicalPath)
            native_fields = {field.name: field for field in actual if field.kind.name == 'Field'}
            for field in schema['fields']:
                native = native_fields[field['name']]
                selected = value.slice(native.bitOffset + native.type.bitWidth - 1, native.bitOffset)
                getattr(result, field['name']).value = self._constant_value(native.type, selected, field['type'])
            return result
        if kind in {'array', 'dyn_array', 'queue'}:
            return [self._constant_value(actual.elementType, item.value, schema['element']) for item in value]
        raise ValueError(f'compile-time values of schema kind {kind!r} are not supported')

    def _add(self, symbol, annotation, scope=None):
        codec = svtypes.materialize_type_spec(annotation, location=symbol)
        schema = svtypes.schema_descriptor(codec).to_dict()['schema']
        if schema['kind'] not in {'enum', 'struct'}:
            # SvTypes normalizes single-dimensional packed shapes to widths.
            # Emit the same public spelling that its source schema describes.
            annotation = _schema_annotation(schema, self.modules.named)
        declaration, = parse_value_exports([{'symbol': symbol,
            'svtypes': svtypes.type_spec_identity(annotation),
            **({'default_class_owners': self._default_owners(symbol)} if self._default_owners(symbol) else {}),
            'schema': schema, **({'source_scope': scope} if scope is not None else {})}])
        annotation = self.modules.add(declaration)
        self.declarations[declaration.key] = declaration
        return annotation

    def annotation(self, actual, *, where, public_symbol=None):
        from .declarations import _source_semantic_type_declaration, _validate_source_value_schema
        from .sv_selection import matches_sv_selector

        symbol, scope = self.source_symbol(actual)
        native_symbol = symbol
        symbol = public_symbol or symbol
        if any(matches_sv_selector(value_key(symbol, scope), pattern) for pattern in self.exclude):
            raise SVXInheritanceError(f'{where} requires excluded SV value type {symbol}')
        key = value_key(symbol, scope)
        if key in self.modules.annotations:
            return self.modules.annotations[key]
        canonical = actual.canonicalType
        if canonical.kind.name in {'EnumType', 'PackedStructType'}:
            visibility = getattr(actual, 'visibility', None)
            if visibility is not None and visibility.name in {'Local', 'Protected'}:
                raise SVXInheritanceError(
                    f'{where}: named value type {symbol} is {visibility.name.lower()}; '
                    'the generated external value bridge requires an accessible public type')
            if actual.kind.name == 'TypeAlias' and actual.targetType.type.kind.name == 'TypeAlias':
                return self._add(symbol, self.annotation(actual.targetType.type, where=where), scope)
            known_origin = self.named_value_origins.get(canonical) or self.class_value_symbols.get(canonical)
            origin = (known_origin[0] if known_origin is not None and known_origin[1] == scope
                      else self.source_symbol(canonical)[0] if canonical.name else native_symbol)
            if symbol != origin:
                annotation = self.modules.annotations.get(value_key(origin, scope))
                if annotation is None:
                    source = actual if not canonical.name and native_symbol == origin else canonical
                    annotation = self.annotation(source, where=where)
                return self._add(symbol, annotation, scope)
            from .scoped_exports import scoped_public_module
            from .source_scopes import source_class_parts
            parts = source_class_parts(symbol, scope)
            if not parts:
                raise SVXInheritanceError(f'{where}: automatic value export currently requires a package type: {symbol}')
            module, name = scoped_public_module(symbol, scope), parts[-1]
            qualname = '.'.join(parts)
            if canonical.kind.name == 'EnumType':
                if canonical.isFourState:
                    raise SVXInheritanceError(f'{where}: SvTypes Enum cannot preserve this four-state enum')
                members = {}
                for member in canonical:
                    if member.kind.name != 'EnumValue':
                        continue
                    if member.value.hasUnknown():
                        raise SVXInheritanceError(f'{where}: enum literal {member.name} has X/Z bits unsupported by SvTypes Enum')
                    members[member.name] = int(member.value.value)
                base = svtypes.Enum[svtypes.Bit[canonical.bitWidth,
                       svtypes.Signed if canonical.isSigned else svtypes.Unsigned]]
                annotation = new_class(name, (base,), {},
                    lambda namespace: namespace.update({'__module__': module, '__qualname__': qualname, **members}))
            else:
                fields = {}
                for field in canonical:
                    if field.kind.name != 'Field':
                        continue
                    binding = _source_semantic_type_declaration(field.type,
                        where=f'{where}.{field.name}', value_annotations=self.value_annotations, value_exports=self)
                    annotation = svtypes.type_spec_from_identity(binding['svtypes'], location=where)
                    fields[field.name] = svtypes.materialize_type_spec(annotation, location=where)
                annotation = type(name, (svtypes.SvStruct,), {'__module__': module, '__qualname__': qualname, **fields})
            _validate_source_value_schema(canonical,
                svtypes.schema_descriptor(annotation).schema, where=where)
            self.named_value_origins.setdefault(canonical, (symbol, scope))
            if scope is None and self._generic_value_owner(canonical):
                self.class_value_symbols.setdefault(canonical, (symbol, scope))
            return self._add(symbol, annotation, scope)
        if canonical.kind.name == 'UnpackedStructType':
            raise SVXInheritanceError(f'{where}: SvTypes SvStruct currently describes packed, not unpacked structs')
        binding = _source_semantic_type_declaration(actual, where=where,
            value_annotations=self.value_annotations, value_exports=self)
        annotation = svtypes.type_spec_from_identity(binding['svtypes'], location=where)
        return self._add(symbol, annotation, scope)

    def select(self, paths, *, types=(), constants=(), callables=(), packages=(), recursive=False, parse_options=None, compilation_unit=False):
        from pyslang.ast import Compilation
        from pyslang.syntax import SyntaxKind
        from .sv_scan import _parse_sources, _pyslang, _lookup_sv_symbol, _token_text, _source_display_name
        from .sv_selection import source_packages, select_package_names, matches_sv_selector as matches

        package_imports = source_packages(paths, parse_options=parse_options, compilation_unit=compilation_unit)
        owned = select_package_names(package_imports, packages, recursive)
        compilation = Compilation()
        names = []

        def typedefs(scope, members):
            for member in members:
                if member.kind == SyntaxKind.ClassDeclaration:
                    typedefs(scope + '::' + _token_text(member.name), member.items)
                elif member.kind == SyntaxKind.TypedefDeclaration:
                    names.append(scope + '::' + _token_text(member.name))
                elif member.kind == SyntaxKind.ClassPropertyDeclaration:
                    if any(_token_text(qualifier) in {'local', 'protected'} for qualifier in member.qualifiers):
                        continue
                    declaration = member.declaration
                    if declaration.kind == SyntaxKind.TypedefDeclaration:
                        names.append(scope + '::' + _token_text(declaration.name))

        for _, tree in _parse_sources(_pyslang(), paths, parse_options=parse_options, compilation_unit=compilation_unit):
            compilation.addSyntaxTree(tree)
            roots = (tree.root,) if tree.root.kind == SyntaxKind.PackageDeclaration else getattr(tree.root, 'members', ())
            for root in roots:
                if root.kind == SyntaxKind.PackageDeclaration:
                    typedefs(root.header.name.valueText, root.members)
        from .sv_frontend import compile_source_trees
        compilation = compile_source_trees(compilation.getSyntaxTrees())
        self.class_lookup = lambda name: _lookup_sv_symbol(compilation, name)
        candidates = {}
        for name in names:
            actual = _lookup_sv_symbol(compilation, name)
            if actual is not None and not actual.canonicalType.isClass:
                candidates[name] = actual
        candidate_packages = set(owned)
        for pattern in (*types, *constants, *callables):
            candidate_packages.update(package for package in package_imports
                if '::' not in pattern or fnmatchcase(package, pattern.split('::')[0]))
        class_constants, class_contexts, inherited_constants, inherited_types = {}, {}, set(), set()
        callable_class_roots = []
        def class_members(native, prefix, owner=None, inherited=False, visiting=()):
            if native in visiting:
                return
            owner = owner or (native, prefix)
            for entry in native:
                forwarded = entry.kind.name == 'TransparentMember'
                member = native.lookupName(entry.name) if forwarded else entry
                if member is None or getattr(getattr(member, 'visibility', None), 'name', '') in {'Local', 'Protected'}:
                    continue
                name = prefix + '::' + entry.name
                if member.kind.name == 'TypeParameter':
                    member = member.typeAlias
                if member.kind.name == 'Parameter':
                    class_constants[name] = member
                    class_contexts[name] = owner
                    if inherited or forwarded:
                        inherited_constants.add(name)
                elif member.kind.name == 'TypeAlias' and not member.canonicalType.isClass:
                    candidates[name] = member
                    class_contexts[name] = owner
                    if inherited or forwarded:
                        inherited_types.add(name)
                elif member.kind.name == 'ClassType':
                    class_members(member, name, owner, inherited or forwarded, (*visiting, native))
                elif member.kind.name == 'TypeAlias' and member.canonicalType.isClass:
                    class_members(member.canonicalType, name, owner, inherited or forwarded, (*visiting, native))
        for package in sorted(candidate_packages):
            native_package = compilation.getPackage(package)
            if native_package is not None:
                for item in native_package:
                    if item.kind.name == 'GenericClassDef' and (types or constants or owned):
                        resolved = native_package.lookupName(item.name)
                        if resolved is None or not getattr(resolved, 'isClass', False):
                            continue
                        native = resolved.canonicalType
                        if any(member.kind.name == 'TypeParameter' and member.targetType.type.isError
                               or member.kind.name == 'Parameter' and not member.isLocalParam and not member.value
                               for member in native):
                            continue
                        callable_class_roots.append((native, item.lexicalPath))
                        class_members(native, item.lexicalPath)
                    elif item.kind.name == 'ClassType':
                        callable_class_roots.append((item, item.lexicalPath))
                        if types or constants or owned:
                            class_members(item, item.lexicalPath)
                    elif item.kind.name == 'TypeAlias' and item.canonicalType.isClass:
                        callable_class_roots.append((item.canonicalType, item.lexicalPath))
                        if types or constants or owned:
                            class_members(item.canonicalType, item.lexicalPath)
        unit_constants = {}
        instance_contexts = {}
        instance_patterns = [pattern for pattern in (*types, *constants)
            if '.' in pattern or not pattern.startswith('$unit') and pattern.split('::', 1)[0] not in package_imports]
        if instance_patterns:
            from .sv_frontend import source_elaboration_mode
            from .sv_inventory import declaration_inventory
            from .source_scopes import selected_native_scopes
            requested = any('.' in pattern for pattern in instance_patterns)
            if not requested:
                inventory = declaration_inventory(paths, parse_options=parse_options,
                    compilation_unit=compilation_unit, kinds=('type', 'constant'))
                requested = any(any(owner['kind'] in {'module', 'interface', 'program', 'generate'}
                                    for owner in item['scope'])
                    and any(fnmatchcase(item['name'], pattern.split('::')[-1]) for pattern in instance_patterns)
                    for item in inventory['declarations'])
            if requested:
                if source_elaboration_mode() == 'packages':
                    raise SVXInheritanceError('instance-owned values require design hierarchy elaboration; use --sv-elaboration all')
                for native, scope in selected_native_scopes(compilation, instance_patterns):
                    local_types, local_constants = self.register_instance(native, scope)
                    candidates.update(local_types)
                    unit_constants.update(local_constants)
                    instance_contexts.update((key, scope) for key in (*local_types, *local_constants))
        want_units = any('::' not in pattern or pattern.split('::', 1)[0] not in package_imports
                         for pattern in (*types, *constants))
        for index, unit in enumerate(compilation.getRoot().compilationUnits if want_units else ()):
            self.unit_indices[unit] = index
            def unit_types(scope):
                for item in scope:
                    if item.kind.name == 'TypeAlias':
                        self.unit_symbols[item] = index
                        if item.canonicalType.lexicalPath == item.lexicalPath:
                            self.unit_symbols[item.canonicalType] = index
                        if (not item.canonicalType.isClass
                                and getattr(getattr(item, 'visibility', None), 'name', '') not in {'Local', 'Protected'}):
                            candidates[f'$unit[{index}]::{item.lexicalPath}'] = item
                    elif item.kind.name == 'ClassType':
                        unit_types(item)
                    elif item.kind.name == 'Parameter':
                        self.unit_symbols[item] = index
                        unit_constants[f'$unit[{index}]::{item.lexicalPath}'] = item
            # Packages have their own scope; do not reinterpret their types as $unit.
            unit_types(unit)

        selected = {name for name in candidates if name.split('::')[0] in owned and name not in inherited_types}
        for pattern in types:
            found = {name for name in candidates if matches(name, pattern)}
            if not found:
                raise SVXInheritanceError(f'SV type selector {pattern!r} matched no package value typedef, $unit value typedef or instance value typedef')
            exact = not any(char in re.sub(r'\[-?[0-9]+\]', '', re.sub(r'^\$unit\[\d+\]', '$unit', pattern)) for char in '*?[')
            if exact and len(found) > 1:
                raise SVXInheritanceError(f'ambiguous SV type {pattern!r}: ' + ', '.join(sorted(map(_source_display_name, found))))
            selected.update(found)
        selected = {name for name in selected if not any(matches(name, pattern) for pattern in self.exclude)}
        if types and not selected:
            raise SVXInheritanceError('SV value export selection is empty after exclusions')
        for name in sorted(selected):
            if name in class_contexts:
                self.register_class_values(*class_contexts[name])
            with self.instance_context(instance_contexts.get(name)):
                self.annotation(candidates[name], where=f'SV value type {name}',
                    public_symbol=name if not name.startswith(('$unit[', '$instance[')) else None)
        if not (constants or callables or owned):
            return
        constant_candidates, callable_candidates = {**unit_constants, **class_constants}, {}
        for package in sorted(candidate_packages):
            native_package = compilation.getPackage(package)
            if native_package is not None:
                for item in native_package:
                    if item.kind.name == 'Parameter':
                        constant_candidates[item.lexicalPath] = item
                    elif item.kind.name == 'Subroutine':
                        callable_candidates[item.lexicalPath] = item
        selected_constants = {name for name in constant_candidates
                              if name.split('::')[0] in owned and name not in inherited_constants}
        for pattern in constants:
            found = {name for name in constant_candidates if matches(name, pattern)}
            if not found:
                raise SVXInheritanceError(f'SV constant selector {pattern!r} matched no package parameter/localparam or $unit parameter/localparam or instance parameter/localparam (including ordinary class-owned declarations)')
            exact = not any(char in re.sub(r'\[-?[0-9]+\]', '', re.sub(r'^\$unit\[\d+\]', '$unit', pattern)) for char in '*?[')
            if exact and len(found) > 1:
                raise SVXInheritanceError(f'ambiguous SV constant {pattern!r}: ' + ', '.join(sorted(map(_source_display_name, found))))
            selected_constants.update(found)
        selected_constants = {name for name in selected_constants if not any(
            matches(name, pattern)
            for pattern in self.exclude_constants)}
        if constants and not selected_constants:
            raise SVXInheritanceError('SV constant export selection is empty after exclusions')
        for name in sorted(selected_constants):
            if name in class_contexts:
                self.register_class_values(*class_contexts[name])
            with self.instance_context(instance_contexts.get(name)):
                self.constant(constant_candidates[name], symbol=name if not name.startswith(('$unit[', '$instance[')) else None)
        selected_callables = {name for name in callable_candidates if name.split('::')[0] in owned}
        for pattern in callables:
            matches = {name for name in callable_candidates if fnmatchcase(
                name if '::' in pattern else name.split('::')[-1], pattern)}
            if not matches:
                raise SVXInheritanceError(f'SV callable selector {pattern!r} matched no package function/task')
            if '::' not in pattern and not any(char in pattern for char in '*?[') and len(matches) > 1:
                raise SVXInheritanceError(f'ambiguous SV callable {pattern!r}: ' + ', '.join(sorted(matches)))
            selected_callables.update(matches)
        selected_callables = {name for name in selected_callables if not any(
            fnmatchcase(name, pattern) or fnmatchcase(name.split('::')[-1], pattern)
            for pattern in self.exclude_callables)}
        if callables and not selected_callables:
            raise SVXInheritanceError('SV callable export selection is empty after exclusions')
        if selected_callables:
            for native, prefix in sorted(callable_class_roots,
                    key=lambda item: (item[0].genericClass is None, item[1])):
                self.register_class_values(native, prefix)
        for name in sorted(selected_callables):
            self.callable(callable_candidates[name])
