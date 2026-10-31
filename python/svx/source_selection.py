"""Replay parser-observed include/library choices without parsing source text."""

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
import hashlib
import json
from pathlib import Path


_recording = ContextVar('svx_source_selection_recording', default=None)
_observations = ContextVar('svx_source_observations', default=None)


@dataclass
class SourceObservations:
    proofs: dict = field(default_factory=dict)
    captures: int = 0
    reuses: int = 0


@contextmanager
def source_observations():
    """Reuse dependency observations only after fresh byte/lookup verification."""
    previous = _observations.get()
    if previous is not None:
        yield previous
        return
    state = SourceObservations()
    token = _observations.set(state)
    try:
        yield state
    finally:
        _observations.reset(token)


def with_source_observations(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with source_observations():
            return function(*args, **kwargs)
    return wrapped


def observed_dependencies(paths, **options):
    """Return proven dependencies, or None to use the original parser path."""
    state = _observations.get()
    if state is None or _recording.get() is not None:
        return None
    paths = tuple(paths)
    context = selection_context(paths, **options)
    key = json.dumps(context, sort_keys=True)
    proof = state.proofs.get(key)
    if proof is not None and validate_selection(proof, context):
        state.reuses += 1
        return {Path(item['path']) for item in proof['files']}
    proof, dependencies = _capture_selection(paths, **options)
    state.captures += 1
    if proof is None:
        state.proofs.pop(key, None)
        return dependencies
    state.proofs[key] = proof
    return {Path(item['path']) for item in proof['files']}


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record_library_query(name, selected):
    state = _recording.get()
    if state is not None:
        key = (name, str(selected) if selected else None)
        if key not in state['library_keys']:
            state['library_keys'].add(key)
            state['libraries'].append({'name': name, 'selected': key[1]})


def record_source_trees(trees):
    state = _recording.get()
    if state is None:
        return
    for _, tree in trees:
        manager = tree.sourceManager
        if id(manager) not in state['manager_ids']:
            state['manager_ids'].add(id(manager))
            state['managers'].append(manager)
        for buffer in manager.getAllBuffers():
            key = (id(manager), buffer.id)
            if key in state['buffer_keys']:
                continue
            state['buffer_keys'].add(key)
            filename = manager.getRawFileName(buffer)
            if not filename or filename.startswith('<'):
                continue
            path = str(Path(filename).resolve())
            # SourceManager includes one terminal NUL outside the physical file.
            data = manager.getSourceText(buffer)
            if not data.endswith('\0'):
                state['replayable'] = False
                continue
            digest = hashlib.sha256(data[:-1].encode('utf-8')).hexdigest()
            if path in state['files'] and state['files'][path] != digest:
                state['replayable'] = False
            state['files'][path] = digest
        for directive in tree.getIncludeDirectives():
            location = manager.getIncludedFrom(directive.buffer.id)
            if manager.isMacroLoc(location):
                state['replayable'] = False
                continue
            parent = manager.getRawFileName(location.buffer)
            if not parent or parent.startswith('<'):
                state['replayable'] = False
                continue
            library = directive.buffer.library
            if library is not None and library.name:
                # Named-library include paths are not an imported CLI contract yet.
                state['replayable'] = False
                continue
            query = {'parent': str(Path(parent).absolute()), 'path': directive.path,
                     'system': directive.isSystem,
                     'selected': str(Path(manager.getRawFileName(directive.buffer.id)).resolve())}
            key = tuple(query.items())
            if key not in state['include_keys']:
                state['include_keys'].add(key)
                state['includes'].append(query)


def _include_directory_identity(path):
    directory = Path(path)
    try:
        return str(directory.resolve(strict=True))
    except (OSError, RuntimeError):
        # Missing a/../b must not be mistaken for an existing b directory.
        return str(directory.absolute())


def selection_context(paths, *, predefines=None, undefines=(), include_dirs=(), compilation_unit=False):
    from .sv_frontend import source_elaboration_mode
    from .sv_library_search import _search
    search = _search.get()
    return {'cwd': str(Path.cwd()), 'sources': [str(Path(path).resolve()) for path in paths],
            'predefines': dict(predefines or {}), 'undefines': list(undefines),
            'include_dirs': [_include_directory_identity(path) for path in include_dirs],
            'compilation_unit': compilation_unit, 'elaboration': source_elaboration_mode(),
            'library_dirs': [str(path) for path in search.directories] if search else [],
            'library_extensions': list(search.extensions) if search else [],
            'top_modules': list(search.top_modules) if search else []}


def capture_selection(paths, **options):
    """Return a replayable selection proof, never an unverified partial proof."""
    return _capture_selection(paths, **options)[0]


def _capture_selection(paths, **options):
    """Keep parsed dependencies when only lookup recording is unreplayable."""
    import pyslang
    from .sv_source_options import _source_dependencies

    paths = tuple(paths)
    context = selection_context(paths, **options)
    state = {'files': {}, 'includes': [], 'libraries': [], 'replayable': True,
             'include_keys': set(), 'library_keys': set(), 'buffer_keys': set(),
             'manager_ids': set(), 'managers': []}
    token = _recording.set(state)
    try:
        dependencies = _source_dependencies(paths, **options)
    finally:
        _recording.reset(token)
    if not state['replayable'] or set(state['files']) != {str(path) for path in dependencies}:
        return None, dependencies
    proof = {'schema_version': 1, 'parser_version': pyslang.__version__, 'context': context,
             'files': [{'path': path, 'sha256': digest} for path, digest in sorted(state['files'].items())],
             'includes': state['includes'], 'libraries': state['libraries']}
    if not validate_selection(proof, context):
        # A changing source/lookup graph must take the fresh-parser fallback.
        return None, None
    return proof, dependencies


def validate_selection(proof, expected_context):
    """Fresh content and native header lookup observations; no shared file cache."""
    import pyslang
    from pyslang import SourceLocation, SourceManager
    from .sv_library_search import resolve_library_file

    try:
        if (not isinstance(proof, dict) or set(proof) != {
                'schema_version', 'parser_version', 'context', 'files', 'includes', 'libraries'}
                or proof['schema_version'] != 1 or proof['parser_version'] != pyslang.__version__
                or proof['context'] != expected_context):
            return False
        files = {}
        for item in proof['files']:
            if (not isinstance(item, dict) or set(item) != {'path', 'sha256'}
                    or not isinstance(item['path'], str) or not Path(item['path']).is_absolute()
                    or item['path'] in files or not isinstance(item['sha256'], str)
                    or len(item['sha256']) != 64 or set(item['sha256']) - set('0123456789abcdef')
                    or str(Path(item['path']).resolve()) != item['path']
                    or file_digest(item['path']) != item['sha256']):
                return False
            files[item['path']] = item['sha256']
        if not set(expected_context['sources']) <= set(files):
            return False
        manager = SourceManager()
        for directory in expected_context['include_dirs']:
            manager.addUserDirectories(directory)
        for query in proof['includes']:
            if (not isinstance(query, dict) or set(query) != {'parent', 'path', 'system', 'selected'}
                    or not isinstance(query['parent'], str) or not Path(query['parent']).is_absolute()
                    or str(Path(query['parent']).resolve()) not in files
                    or not isinstance(query['path'], str) or '\0' in query['path']
                    or not isinstance(query['system'], bool) or query['selected'] not in files):
                return False
            parent = manager.readSource(query['parent'])
            selected = manager.readHeader(query['path'], SourceLocation(parent.id, 0), None, query['system'])
            if str(Path(manager.getRawFileName(selected.id)).resolve()) != query['selected']:
                return False
        for query in proof['libraries']:
            if (not isinstance(query, dict) or set(query) != {'name', 'selected'}
                    or not isinstance(query['name'], str) or not query['name'].isascii()
                    or not query['name'].isidentifier()
                    or query['selected'] is not None and query['selected'] not in files):
                return False
            selected = resolve_library_file(query['name'],
                map(Path, expected_context['library_dirs']), expected_context['library_extensions'])
            if (str(selected) if selected else None) != query['selected']:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False
