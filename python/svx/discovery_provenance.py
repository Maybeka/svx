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
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'path'}
            or value['schema_version'] != DISCOVERY_PROVENANCE_VERSION
            or not _relative_path(value['path'])):
        raise SVXInheritanceError('invalid discovery_provenance marker')
    return DiscoveryProvenance(value['schema_version'], value['path'])


def discovery_contract_digest(data: dict) -> str:
    contract = {key: value for key, value in data.items() if key != 'discovery_provenance'}
    encoded = json.dumps(contract, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _configuration(value) -> bool:
    if not isinstance(value, dict):
        return False
    paths = {'sv_declarations', 'sv_sources', 'sv_dependencies', 'python_sources', 'sv_include_dirs'}
    names = {'python_modules', 'sv_undefines'}
    if set(value) - paths - names - {'sv_predefines', 'source_mode', 'python_selections', 'python_namespaces', 'sv_build', 'sv_selection', 'sv_elaboration'}:
        return False
    elaboration = value.get('sv_elaboration', 'all')
    if not isinstance(elaboration, str) or elaboration not in {'all', 'packages'}:
        return False
    selection = value.get('sv_selection')
    if selection is not None:
        if (not isinstance(selection, dict)
                or not {'classes', 'packages', 'exclude_classes', 'recursive_packages'} <= set(selection)
                or set(selection) - {'classes', 'packages', 'exclude_classes', 'recursive_packages', 'members', 'exclude_members', 'types', 'exclude_types', 'constants', 'exclude_constants', 'callables', 'exclude_callables'}
                or not isinstance(selection['recursive_packages'], bool)):
            return False
        for key in ('classes', 'packages', 'exclude_classes', 'members', 'exclude_members', 'types', 'exclude_types', 'constants', 'exclude_constants', 'callables', 'exclude_callables'):
            if (not isinstance(selection.get(key, []), list)
                    or any(not isinstance(item, str) or not item for item in selection.get(key, []))):
                return False
    selections = value.get('python_selections', [])
    if (not isinstance(selections, list) or any(
            not isinstance(item, dict) or set(item) != {'module', 'path'}
            or not isinstance(item['module'], str) or not item['module']
            or any(not part for part in item['module'].split('.'))
            or not _relative_path(item['path']) for item in selections)):
        return False
    namespaces = value.get('python_namespaces', [])
    if (not isinstance(namespaces, list) or any(
            not isinstance(item, dict) or set(item) != {'module', 'paths'}
            or not isinstance(item['module'], str) or not item['module']
            or any(not part for part in item['module'].split('.'))
            or not isinstance(item['paths'], list) or not item['paths']
            or any(path != '.' and not _relative_path(path) for path in item['paths'])
            for item in namespaces)):
        return False
    for key in paths | names:
        items = value.get(key, [])
        if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
            return False
        if key in paths and any(not _relative_path(item) and not (
                key == 'sv_include_dirs' and item == '.') for item in items):
            return False
    defines = value.get('sv_predefines', {})
    if (not isinstance(defines, dict) or any(not isinstance(key, str) or not key
            or val is not None and not isinstance(val, str) for key, val in defines.items())):
        return False
    mode = value.get('source_mode', 'separate-parse-inputs')
    return isinstance(mode, str) and mode in {
        'separate-parse-inputs', 'shared-compilation-unit'}


def _validate_python_selections(configuration: dict, root: Path, sources: set[Path]) -> None:
    if configuration.get('python_modules') and 'python_selections' not in configuration:
        raise SVXInheritanceError('discovery Python selection inventory is missing; rerun inheritance-manifest')
    importlib.invalidate_caches()
    seen = set()
    namespaces = {}
    for item in configuration.get('python_selections', []):
        name = item['module']
        expected = (root / item['path']).resolve()
        if name in seen or expected not in sources:
            raise SVXInheritanceError('invalid discovery Python selection inventory')
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
    if set(configuration.get('python_modules', [])) - seen:
        raise SVXInheritanceError('discovery Python entry selection is missing; rerun inheritance-manifest')
    expected_namespaces = {}
    for item in configuration.get('python_namespaces', []):
        if item['module'] in expected_namespaces:
            raise SVXInheritanceError('invalid discovery Python namespace inventory')
        expected_namespaces[item['module']] = tuple(dict.fromkeys(
            (root / path).resolve() for path in item['paths']))
    if namespaces != expected_namespaces:
        raise SVXInheritanceError(
            'discovery Python namespace selection changed; rerun inheritance-manifest with current import paths')


def validate_discovery_provenance(data: dict, manifest_path: Path | None, *,
                                  fingerprints: dict[Path, str] | None = None) -> tuple[Path, ...]:
    """Validate evidence before parsing classes or materializing codec factories.

    Paths are relative to the manifest directory so the complete source tree can
    move together. Absence is an explicit legacy/handwritten contract, not proof
    of source discovery. A present marker cannot silently fall back to that mode.
    """
    if 'discovery_provenance' in data and data['discovery_provenance'] is None:
        raise SVXInheritanceError('invalid discovery_provenance marker')
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
            f'cannot read discovery provenance {evidence}; rerun inheritance-manifest') from error
    if (not isinstance(record, dict)
            or set(record) != {'schema_version', 'contract_sha256', 'sources', 'configuration'}
            or record['schema_version'] != DISCOVERY_PROVENANCE_VERSION
            or not _digest(record['contract_sha256'])
            or not _configuration(record['configuration'])
            or not isinstance(record['sources'], list) or not record['sources']):
        raise SVXInheritanceError(f'invalid discovery provenance: {evidence}')
    if record['contract_sha256'] != discovery_contract_digest(data):
        raise SVXInheritanceError(
            f'discovery provenance does not match manifest contract: {evidence}; '
            'rerun inheritance-manifest')
    sources = []
    seen = {evidence, manifest_path.resolve()}
    for item in record['sources']:
        if (not isinstance(item, dict) or set(item) != {'path', 'sha256'}
                or not _relative_path(item['path']) or not _digest(item['sha256'])):
            raise SVXInheritanceError(f'invalid discovery source record: {evidence}')
        path = (root / item['path']).resolve()
        if path in seen:
            raise SVXInheritanceError(f'duplicate or generated discovery source: {path}')
        seen.add(path)
        sources.append((path, item['sha256']))
    for path, digest in sources:
        try:
            current = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise SVXInheritanceError(
                f'discovery source is missing or unreadable: {path}; '
                'rerun inheritance-manifest') from error
        if current != digest:
            raise SVXInheritanceError(
                f'discovery source changed: {path}; rerun inheritance-manifest')
    configuration = record['configuration']
    if 'sv_build' in configuration:
        from .compile_config import replay_build_record
        imported = replay_build_record(configuration['sv_build'], root)
        if not set(imported.inputs) <= {path for path, _ in sources}:
            raise SVXInheritanceError('imported build input inventory is missing')
    _validate_python_selections(configuration, root, {path for path, _ in sources})
    if configuration.get('sv_sources'):
        if 'sv_dependencies' not in configuration:
            raise SVXInheritanceError(
                'discovery SV dependency inventory is missing; rerun inheritance-manifest')
        expected = [(root / name).resolve() for name in configuration['sv_dependencies']]
        if len(expected) != len(set(expected)) or not set(expected) <= {path for path, _ in sources}:
            raise SVXInheritanceError(f'invalid discovery SV dependency inventory: {evidence}')
        from .sv_source_options import _source_dependencies
        from .sv_library_search import library_search
        from .compile_config import CompileConfiguration
        from .sv_frontend import source_elaboration
        context = imported if 'sv_build' in configuration else CompileConfiguration([], [], {}, [], [])
        with library_search(context), source_elaboration(configuration.get('sv_elaboration', 'all')):
            selected = _source_dependencies(
                [root / name for name in configuration['sv_sources']],
                predefines=configuration.get('sv_predefines', {}),
                undefines=configuration.get('sv_undefines', []),
                include_dirs=[root / name for name in configuration.get('sv_include_dirs', [])],
                compilation_unit=configuration.get('source_mode') == 'shared-compilation-unit')
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
