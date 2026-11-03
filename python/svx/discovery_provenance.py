"""Versioned discovery evidence, separate from generated class targets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
from importlib.machinery import PathFinder, SourceFileLoader
import json
import sys
from pathlib import Path, PurePosixPath
from posixpath import normpath

from .errors import SVXInheritanceError


DISCOVERY_PROVENANCE_VERSION = '1.0.0'


@dataclass(frozen=True)
class DiscoveryProvenance:
    schema_version: str
    path: str

    def as_dict(self) -> dict:
        return {'schema_version': self.schema_version, 'path': self.path}


def _relative_path(value) -> bool:
    return (isinstance(value, str) and bool(value) and '\0' not in value
            and value != '.' and not PurePosixPath(value).is_absolute()
            and PurePosixPath(value).as_posix() == value and normpath(value) == value)


def _digest(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and set(value) <= set('0123456789abcdef'))


def discovery_marker(value) -> DiscoveryProvenance | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise SVXInheritanceError('invalid discovery_provenance marker: expected an object')
    expected = {'schema_version', 'path'}
    if set(value) != expected:
        raise SVXInheritanceError(f'invalid discovery_provenance marker: missing fields {sorted(expected - set(value))}; unexpected fields {sorted(set(value) - expected)}')
    if value['schema_version'] != DISCOVERY_PROVENANCE_VERSION:
        raise SVXInheritanceError(f'invalid discovery_provenance marker: schema_version must be {DISCOVERY_PROVENANCE_VERSION!r}, got {value["schema_version"]!r}')
    if not _relative_path(value['path']):
        raise SVXInheritanceError(f'invalid discovery_provenance marker: path must be a normalized nonempty relative path, got {value["path"]!r}')
    return DiscoveryProvenance(value['schema_version'], value['path'])


def discovery_contract_digest(data: dict) -> str:
    contract = {key: value for key, value in data.items() if key != 'discovery_provenance'}
    encoded = json.dumps(contract, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _configuration_error(value) -> str | None:
    if not isinstance(value, dict):
        return 'configuration must be an object'
    paths = {'sv_declarations', 'sv_sources', 'sv_dependencies', 'python_sources', 'sv_include_dirs',
             'sv_excluded_sources'}
    names = {'python_modules', 'sv_undefines'}
    unknown = set(value) - paths - names - {'sv_predefines', 'source_mode', 'python_selections', 'python_namespaces', 'sv_build', 'sv_selection', 'sv_elaboration'}
    if unknown:
        return f'configuration has unexpected fields {sorted(unknown)}'
    elaboration = value.get('sv_elaboration', 'all')
    if not isinstance(elaboration, str) or elaboration not in {'all', 'packages'}:
        return f'configuration.sv_elaboration must be "all" or "packages", got {elaboration!r}'
    selection = value.get('sv_selection')
    if selection is not None:
        if not isinstance(selection, dict):
            return 'configuration.sv_selection must be an object'
        required = {'classes', 'packages', 'exclude_classes', 'recursive_packages'}
        allowed = required | {'members', 'exclude_members', 'types', 'exclude_types', 'constants', 'exclude_constants', 'callables', 'exclude_callables'}
        if required - set(selection) or set(selection) - allowed:
            return f'configuration.sv_selection has missing fields {sorted(required - set(selection))} and unexpected fields {sorted(set(selection) - allowed)}'
        if not isinstance(selection['recursive_packages'], bool):
            return 'configuration.sv_selection.recursive_packages must be a boolean'
        for key in ('classes', 'packages', 'exclude_classes', 'members', 'exclude_members', 'types', 'exclude_types', 'constants', 'exclude_constants', 'callables', 'exclude_callables'):
            items = selection.get(key, [])
            if not isinstance(items, list):
                return f'configuration.sv_selection.{key} must be a list'
            invalid = [index for index, item in enumerate(items) if not isinstance(item, str) or not item]
            if invalid:
                return f'configuration.sv_selection.{key} contains empty or non-string values at indices {invalid}'
    selections = value.get('python_selections', [])
    if not isinstance(selections, list):
        return 'configuration.python_selections must be a list'
    for index, item in enumerate(selections):
        prefix = f'configuration.python_selections[{index}]'
        if not isinstance(item, dict) or set(item) != {'module', 'path'}:
            return f'{prefix} must be an object with module and path fields'
        if not isinstance(item['module'], str) or not item['module'] or any(not part for part in item['module'].split('.')):
            return f'{prefix}.module must be a nonempty dotted module name'
        if not _relative_path(item['path']):
            return f'{prefix}.path must be a normalized nonempty relative path, got {item["path"]!r}'
    namespaces = value.get('python_namespaces', [])
    if not isinstance(namespaces, list):
        return 'configuration.python_namespaces must be a list'
    for index, item in enumerate(namespaces):
        prefix = f'configuration.python_namespaces[{index}]'
        if not isinstance(item, dict) or set(item) != {'module', 'paths'}:
            return f'{prefix} must be an object with module and paths fields'
        if not isinstance(item['module'], str) or not item['module'] or any(not part for part in item['module'].split('.')):
            return f'{prefix}.module must be a nonempty dotted module name'
        if not isinstance(item['paths'], list) or not item['paths']:
            return f'{prefix}.paths must be a nonempty list'
        for path_index, path in enumerate(item['paths']):
            if path != '.' and not _relative_path(path):
                return f'{prefix}.paths[{path_index}] must be a normalized relative path, got {path!r}'
    for key in sorted(paths | names):
        items = value.get(key, [])
        if not isinstance(items, list):
            return f'configuration.{key} must be a list'
        for index, item in enumerate(items):
            if not isinstance(item, str) or not item:
                return f'configuration.{key}[{index}] must be a nonempty string, got {item!r}'
            if key in paths and not _relative_path(item) and not (key == 'sv_include_dirs' and item == '.'):
                return f'configuration.{key}[{index}] must be a normalized relative path, got {item!r}'
    defines = value.get('sv_predefines', {})
    if not isinstance(defines, dict):
        return 'configuration.sv_predefines must be an object'
    for key, val in defines.items():
        if not isinstance(key, str) or not key or val is not None and not isinstance(val, str):
            return f'configuration.sv_predefines entry {key!r} must have a nonempty name and a string or null value, got {val!r}'
    mode = value.get('source_mode', 'separate-parse-inputs')
    if not isinstance(mode, str) or mode not in {'separate-parse-inputs', 'shared-compilation-unit'}:
        return f'configuration.source_mode must be "separate-parse-inputs" or "shared-compilation-unit", got {mode!r}'
    return None


def _configuration(value) -> bool:
    return _configuration_error(value) is None


def _validate_python_selections(configuration: dict, root: Path, sources: set[Path]) -> None:
    if configuration.get('python_modules') and 'python_selections' not in configuration:
        raise SVXInheritanceError('discovery Python selection inventory is missing; rerun inheritance-manifest')
    importlib.invalidate_caches()
    seen = set()
    namespaces = {}
    for item in configuration.get('python_selections', []):
        name = item['module']
        expected = (root / item['path']).resolve()
        if name in seen:
            raise SVXInheritanceError(f'invalid discovery Python selection inventory: duplicate module {name!r}')
        if expected not in sources:
            raise SVXInheritanceError(f'invalid discovery Python selection inventory: module {name!r} source {expected} is absent from sources')
        seen.add(name)
        search = sys.path
        spec = None
        parts = name.split('.')
        # Resolve package locations without running initializers or trusting
        # cached __path__ values from an earlier import selection.
        for index in range(len(parts)):
            # A qualified namespace spec assumes its parent is in sys.modules.
            # Resolve one component against an explicit frozen search path instead.
            spec = PathFinder.find_spec(parts[index], search)
            if spec is None:
                break
            if index + 1 < len(parts):
                locations = spec.submodule_search_locations
                if locations is None:
                    spec = None
                    break
                search = tuple(locations)
                if spec.origin is None:
                    namespaces['.'.join(parts[:index + 1])] = tuple(dict.fromkeys(
                        Path(path).resolve() for path in search))
        if (spec is None or not isinstance(spec.loader, SourceFileLoader)
                or not spec.origin or Path(spec.origin).resolve() != expected):
            selected = getattr(spec, 'origin', None)
            raise SVXInheritanceError(
                f'discovery Python selection changed: {name}; expected {expected}, '
                f'selected {selected}; rerun inheritance-manifest with current import paths')
    missing = set(configuration.get('python_modules', [])) - seen
    if missing:
        raise SVXInheritanceError(f'discovery Python entry selection is missing for {sorted(missing)}; rerun inheritance-manifest')
    expected_namespaces = {}
    for item in configuration.get('python_namespaces', []):
        if item['module'] in expected_namespaces:
            raise SVXInheritanceError(f'invalid discovery Python namespace inventory: duplicate module {item["module"]!r}')
        expected_namespaces[item['module']] = tuple(dict.fromkeys(
            (root / path).resolve() for path in item['paths']))
    if namespaces != expected_namespaces:
        changed = sorted(name for name in set(namespaces) | set(expected_namespaces)
                         if namespaces.get(name) != expected_namespaces.get(name))
        raise SVXInheritanceError(
            f'discovery Python namespace selection changed for {changed}; rerun inheritance-manifest with current import paths')


def validate_discovery_provenance(data: dict, manifest_path: Path | None, *,
                                  fingerprints: dict[Path, str] | None = None) -> tuple[Path, ...]:
    """Validate evidence before parsing classes or materializing codec factories.

    Paths are relative to the manifest directory so the complete source tree can
    move together. Absence is an explicit legacy/handwritten contract, not proof
    of source discovery. A present marker cannot silently fall back to that mode.
    """
    if 'discovery_provenance' in data and data['discovery_provenance'] is None:
        raise SVXInheritanceError('invalid discovery_provenance marker: null is not allowed; omit the field for a handwritten manifest')
    marker = discovery_marker(data.get('discovery_provenance'))
    if marker is None:
        return ()
    if manifest_path is None:
        raise SVXInheritanceError(
            'discovery_provenance requires manifest file context; use load_manifest')
    root = manifest_path.resolve().parent
    evidence = (root / marker.path).resolve()
    if evidence == manifest_path.resolve():
        raise SVXInheritanceError('discovery_provenance cannot reference the manifest itself')
    try:
        evidence_bytes = evidence.read_bytes()
        record = json.loads(evidence_bytes.decode('utf-8'))
    except (OSError, ValueError, UnicodeError) as error:
        raise SVXInheritanceError(
            f'cannot read discovery provenance {evidence}: {error}; rerun inheritance-manifest') from error
    prefix = f'invalid discovery provenance: {evidence}'
    if not isinstance(record, dict):
        raise SVXInheritanceError(f'{prefix}: root must be an object')
    required = {'schema_version', 'contract_sha256', 'sources', 'configuration'}
    if set(record) != required:
        raise SVXInheritanceError(f'{prefix}: missing fields {sorted(required - set(record))}; unexpected fields {sorted(set(record) - required)}')
    if record['schema_version'] != DISCOVERY_PROVENANCE_VERSION:
        raise SVXInheritanceError(f'{prefix}: schema_version must be {DISCOVERY_PROVENANCE_VERSION!r}, got {record["schema_version"]!r}')
    if not _digest(record['contract_sha256']):
        raise SVXInheritanceError(f'{prefix}: contract_sha256 must be a 64-character lowercase hexadecimal SHA-256 digest')
    configuration_error = _configuration_error(record['configuration'])
    if configuration_error:
        raise SVXInheritanceError(f'{prefix}: {configuration_error}')
    if not isinstance(record['sources'], list) or not record['sources']:
        raise SVXInheritanceError(f'{prefix}: sources must be a nonempty list')
    if record['contract_sha256'] != discovery_contract_digest(data):
        raise SVXInheritanceError(
            f'discovery provenance does not match manifest contract: {evidence}; '
            'rerun inheritance-manifest')
    sources = []
    seen = {evidence, manifest_path.resolve()}
    for index, item in enumerate(record['sources']):
        source_prefix = f'invalid discovery source record: {evidence}: sources[{index}]'
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise SVXInheritanceError(f'{source_prefix} must be an object with path and sha256 fields')
        if not _relative_path(item['path']):
            raise SVXInheritanceError(f'{source_prefix}.path must be a normalized nonempty relative path, got {item["path"]!r}')
        if not _digest(item['sha256']):
            raise SVXInheritanceError(f'{source_prefix}.sha256 must be a 64-character lowercase hexadecimal SHA-256 digest')
        path = (root / item['path']).resolve()
        if path in seen:
            raise SVXInheritanceError(f'duplicate or generated discovery source: {path}')
        seen.add(path)
        sources.append((path, item['sha256']))
    configuration = record['configuration']
    expected = None
    if configuration.get('sv_sources'):
        if 'sv_dependencies' not in configuration:
            raise SVXInheritanceError(
                'discovery SV dependency inventory is missing; rerun inheritance-manifest')
        expected = [(root / name).resolve() for name in configuration['sv_dependencies']]
        if len(expected) != len(set(expected)):
            duplicates = sorted({str(path) for path in expected if expected.count(path) > 1})
            raise SVXInheritanceError(f'invalid discovery SV dependency inventory: {evidence}: duplicate paths {duplicates}')
        missing = set(expected) - {path for path, _ in sources}
        if missing:
            raise SVXInheritanceError(f'invalid discovery SV dependency inventory: {evidence}: paths absent from sources {sorted(map(str, missing))}')
    # With no Python selection callbacks, a fresh dependency replay below can
    # certify SV bytes and lookup decisions together instead of reading twice.
    replay_bytes = expected is not None and not any(configuration.get(key) for key in
        ('python_modules', 'python_selections', 'python_namespaces'))
    sv_paths = set(expected or ())

    def verify_source(path, digest):
        try:
            current = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise SVXInheritanceError(
                f'discovery source is missing or unreadable: {path}; '
                'rerun inheritance-manifest') from error
        if current != digest:
            raise SVXInheritanceError(
                f'discovery source changed: {path}; rerun inheritance-manifest')

    for path, digest in sources:
        if not replay_bytes or path not in sv_paths:
            verify_source(path, digest)
    if 'sv_build' in configuration:
        from .compile_config import replay_build_record
        imported = replay_build_record(configuration['sv_build'], root)
        missing = set(imported.inputs) - {path for path, _ in sources}
        if missing:
            raise SVXInheritanceError(f'imported build input inventory is missing: {sorted(map(str, missing))}')
    _validate_python_selections(configuration, root, {path for path, _ in sources})
    if configuration.get('sv_sources'):
        from .sv_source_options import _source_dependencies
        from .sv_library_search import library_search
        from .compile_config import CompileConfiguration
        from .sv_frontend import source_elaboration
        context = imported if 'sv_build' in configuration else CompileConfiguration([], [], {}, [], [])
        with library_search(context), source_elaboration(configuration.get('sv_elaboration', 'all')):
            paths = [root / name for name in configuration['sv_sources']]
            options = dict(predefines=configuration.get('sv_predefines', {}),
                           undefines=configuration.get('sv_undefines', []),
                           include_dirs=[root / name for name in configuration.get('sv_include_dirs', [])],
                           compilation_unit=configuration.get('source_mode') == 'shared-compilation-unit')
            certified = None
            if replay_bytes:
                from .source_selection import validated_selection_fingerprints
                certified = validated_selection_fingerprints(paths, **options)
                for path, digest in sources:
                    if path in sv_paths:
                        if certified is None or path not in certified:
                            verify_source(path, digest)
                        elif certified[path] != digest:
                            raise SVXInheritanceError(
                                f'discovery source changed: {path}; rerun inheritance-manifest')
            selected = set(certified) if certified is not None else _source_dependencies(paths, **options)
        if selected != set(expected):
            added = ', '.join(str(path) for path in sorted(selected - set(expected)))
            removed = ', '.join(str(path) for path in sorted(set(expected) - selected))
            raise SVXInheritanceError(
                'discovery dependency selection changed; rerun inheritance-manifest'
                + (f'; added: {added}' if added else '')
                + (f'; removed: {removed}' if removed else ''))
    if fingerprints is not None:
        fingerprints.update({path: digest for path, digest in sources})
        fingerprints[evidence] = hashlib.sha256(evidence_bytes).hexdigest()
    return (evidence, *(path for path, _ in sources))
