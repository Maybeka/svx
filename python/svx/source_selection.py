"""Command-owned dependency proofs and freshly validated raw syntax sharing."""

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from copy import deepcopy
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
    parse_options: dict = field(default_factory=dict)
    syntax: dict = field(default_factory=dict)
    syntax_reuses: int = 0
    source_copy_reuses: int = 0


@dataclass(frozen=True)
class _OwnedSyntax:
    proof: dict
    trees: tuple
    source_manager: object
    owners: tuple
    root_trees: tuple = ()
    root_buffers: tuple = ()
    class_fact_tables: dict = field(default_factory=dict)


def _parse_options_fingerprint(options):
    try:
        preprocessor, lexer = options.preprocessorOptions, options.lexerOptions
        if (options.parserOptions is not None or options.compilationOptions is not None
                or lexer.commentHandlers or preprocessor.keywordMapping or preprocessor.ignoreDirectives):
            return None
        return (tuple(preprocessor.predefines), tuple(preprocessor.undefines),
                tuple(map(str, preprocessor.additionalIncludePaths)), str(preprocessor.predefineSource),
                preprocessor.maxIncludeDepth, str(preprocessor.languageVersion),
                lexer.enableLegacyProtect, lexer.maxErrors, str(lexer.languageVersion))
    except (AttributeError, TypeError):
        return None


def remember_parse_options(options, predefines, undefines, include_dirs, discover_proxies):
    state = _observations.get()
    if state is not None:
        state.parse_options[id(options)] = (
            options, _parse_options_fingerprint(options),
            dict(predefines or {}), tuple(undefines), tuple(include_dirs), discover_proxies)


def _syntax_context(paths, options, compilation_unit):
    state = _observations.get()
    entry = state.parse_options.get(id(options)) if state is not None else None
    if (entry is None or entry[0] is not options or entry[1] is None
            or _parse_options_fingerprint(options) != entry[1]):
        return None
    context = selection_context(paths, predefines=entry[2], undefines=entry[3],
                                include_dirs=entry[4], compilation_unit=compilation_unit)
    # Keep exact parser options; physical source identity follows the frontend's
    # default canonical/proximate filename policy (also used by dependency proofs).
    key = json.dumps({'context': context, 'options': entry[1],
                      'proxy_discovery': entry[5]}, sort_keys=True)
    return key, context


def record_raw_syntax(paths, options, compilation_unit, trees, source_manager, owners):
    recording = _recording.get()
    context = _syntax_context(paths, options, compilation_unit)
    if recording is not None and context is not None:
        recording.setdefault('syntax', []).append((context, tuple(trees), source_manager, owners))


def record_source_roots(paths, options, compilation_unit, trees, manager):
    """Retain explicit roots before a library loader reparses or adds units."""
    recording = _recording.get()
    context = _syntax_context(paths, options, compilation_unit)
    if recording is None or context is None:
        return
    expected = {str(Path(path).resolve()) for path in paths}
    buffers = {}
    for buffer in manager.getAllBuffers():
        filename = manager.getRawFileName(buffer)
        if not filename or filename.startswith('<') or manager.getIncludedFrom(buffer):
            continue
        path = str(Path(filename).resolve())
        if path in expected:
            if path in buffers and buffers[path] != buffer:
                return  # Ambiguous ownership is not suitable for source edits.
            buffers[path] = buffer
    if set(buffers) == expected:
        recording.setdefault('roots', {})[(context[0], id(manager))] = (tuple(trees), tuple(buffers.items()))


def borrow_source_copy_syntax(sources, options, compilation_unit):
    """Borrow only when the caller's exact text still matches physical buffers."""
    snapshot = borrow_raw_syntax(tuple(map(Path, sources)), options, compilation_unit)
    if snapshot is None or not snapshot.root_trees:
        return None
    roots = list(sources)[:1] if compilation_unit else list(sources)
    if [Path(path).resolve() for path, _ in snapshot.root_trees] != [Path(path).resolve() for path in roots]:
        return None
    retained = dict(snapshot.root_buffers)
    buffers = {}
    for filename, text in sources.items():
        buffer = retained.get(str(Path(filename).resolve()))
        if buffer is None or snapshot.source_manager.getSourceText(buffer) != text + '\0':
            return None
        buffers[filename] = buffer
    _observations.get().source_copy_reuses += 1
    return snapshot, buffers


def borrow_raw_syntax(paths, options, compilation_unit, *, required_manager=None):
    state = _observations.get()
    context = _syntax_context(paths, options, compilation_unit)
    if state is None or _recording.get() is not None or context is None:
        return None
    key, expected = context
    snapshot = state.syntax.get(key)
    if snapshot is None:
        return None
    if not validate_selection(snapshot.proof, expected):
        state.syntax.pop(key, None)
        return None
    if required_manager is not None and snapshot.source_manager is not required_manager:
        return None
    state.syntax_reuses += 1
    return snapshot


@contextmanager
def source_observations():
    """Own proofs and syntax until command exit; every cross-phase borrow verifies."""
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


def validated_selection_fingerprints(paths, **options):
    """Freshly replay an existing proof; never parse or cache content hashes."""
    state = _observations.get()
    if state is None or _recording.get() is not None:
        return None
    context = selection_context(tuple(paths), **options)
    proof = state.proofs.get(json.dumps(context, sort_keys=True))
    if proof is None or not validate_selection(proof, context):
        return None
    return {Path(item['path']): item['sha256'] for item in proof['files']}


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
    observations = _observations.get()
    if observations is not None:
        for (key, expected), trees, manager, owners in state.get('syntax', ()):
            if expected == context:
                roots, buffers = state.get('roots', {}).get((key, id(manager)), ((), ()))
                observations.syntax[key] = _OwnedSyntax(deepcopy(proof), trees, manager, owners,
                                                       root_trees=roots, root_buffers=buffers)
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
