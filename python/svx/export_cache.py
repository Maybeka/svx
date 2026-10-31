"""Opt-in, source-certified no-op export reuse; cached data is never executed."""

import argparse
from contextlib import contextmanager
import hashlib
from io import StringIO
import json
from pathlib import Path, PurePosixPath
import platform
import sys

from .errors import SVXInheritanceError
from .source_selection import capture_selection, file_digest, selection_context, validate_selection


SCHEMA = 'https://svx.dev/schema/export-cache/v1'


def _digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _framework():
    import svx
    import svtypes
    import pyslang
    records = []
    for module in (svx, svtypes, pyslang):
        for directory in module.__path__:
            if not Path(directory).is_dir():
                raise OSError(f'framework location is not a fingerprintable directory: {directory}')
            count = len(records)
            for path in sorted(Path(directory).rglob('*')):
                if path.suffix in {'.py', '.so', '.pyd', '.dll', '.dylib'} and path.is_file():
                    records.append((str(path.resolve()), file_digest(path)))
            if len(records) == count:
                raise OSError(f'framework code fingerprint is unavailable: {directory}')
    return _digest({'python': sys.version, 'platform': platform.platform(), 'files': records,
                    'versions': {module.__name__: getattr(module, '__version__', None)
                                 for module in (svx, svtypes, pyslang)}})


def _prepare(args):
    from .cli import _sv_macro_config
    prepared = argparse.Namespace(**vars(args))
    options = _sv_macro_config(prepared)
    request = {key: value for key, value in vars(args).items()
               if not key.startswith('_') and key not in {'func', 'debug', 'check', 'incremental', 'refresh_cache'}}
    request.update(cwd=str(Path.cwd()), output_root=str(Path(args.out).resolve()), framework=_framework(),
                   build=prepared._sv_build_configuration.as_dict(Path.cwd()),
                   build_inputs=[(str(path), file_digest(path)) for path in prepared._sv_build_configuration.inputs],
                   options=options)
    return prepared, options, _digest(request)


@contextmanager
def _selection_scope(prepared):
    from .sv_frontend import source_elaboration
    from .sv_library_search import library_search
    with source_elaboration(prepared.sv_elaboration), library_search(prepared._sv_build_configuration):
        yield


def _source_options(options):
    return {'predefines': options['sv_predefines'], 'undefines': options['sv_undefines'],
            'include_dirs': options['sv_include_dirs'], 'compilation_unit': options['sv_compilation_unit']}


def _safe_output(root, name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or path.as_posix() != name
            or not (root / name).resolve().is_relative_to(root.resolve())):
        raise ValueError('cache output escapes export directory')
    return root / name


def _outputs_match(root, records):
    try:
        if not isinstance(records, list) or not records:
            return False
        seen = set()
        for item in records:
            if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
                return False
            path = _safe_output(root, item['path'])
            resolved = path.resolve()
            if resolved in seen or not path.is_file() or file_digest(path) != item['sha256']:
                return False
            seen.add(resolved)
        return True
    except (OSError, TypeError, ValueError, KeyError):
        return False


def _snapshot(root, args, options, proof):
    from .discovery_provenance import discovery_contract_digest

    manifest = root / 'inheritance.json'
    evidence = root / 'inheritance.json.svx-discovery.json'
    artifact = root / 'artifacts.json'
    model = json.loads(manifest.read_text(encoding='utf-8'))
    record = json.loads(evidence.read_text(encoding='utf-8'))
    inventory = json.loads(artifact.read_text(encoding='utf-8'))
    configuration = record['configuration']
    if record['contract_sha256'] != discovery_contract_digest(model):
        raise ValueError('manifest/provenance changed during cache observation')
    selected = configuration['sv_selection']
    names = {'classes': 'sv_class', 'packages': 'sv_package', 'exclude_classes': 'exclude_class',
             'recursive_packages': 'recursive_packages', 'members': 'member', 'exclude_members': 'exclude_member',
             'types': 'sv_type', 'exclude_types': 'exclude_type', 'constants': 'sv_constant',
             'exclude_constants': 'exclude_constant', 'callables': 'sv_callable', 'exclude_callables': 'exclude_callable'}
    if any(selected.get(key, []) != getattr(args, attribute) for key, attribute in names.items()):
        raise ValueError('export selection changed during cache observation')
    expected_files = {item['path']: item['sha256'] for item in proof['files']}
    observed = {str((root / item['path']).resolve()): item['sha256'] for item in record['sources']}
    if (not all(observed.get(path) == digest for path, digest in expected_files.items())
            or {str((root / path).resolve()) for path in configuration['sv_dependencies']} != set(expected_files)
            or [str((root / path).resolve()) for path in configuration['sv_sources']] != proof['context']['sources']
            or configuration.get('sv_elaboration', 'all') != args.sv_elaboration
            or configuration['sv_predefines'] != options['sv_predefines']
            or configuration['sv_undefines'] != sorted(set(options['sv_undefines']))
            or [str((root / path).resolve()) for path in configuration['sv_include_dirs']] !=
               [str(Path(path).resolve()) for path in options['sv_include_dirs']]
            or configuration['source_mode'] != ('shared-compilation-unit' if options['sv_compilation_unit'] else 'separate-parse-inputs')):
        raise ValueError('source observations no longer match generated provenance')
    if inventory['generation_inputs']['manifest']['sha256'] != file_digest(manifest):
        raise ValueError('artifact manifest changed during cache observation')
    sv = [item['path'] for item in inventory['artifacts'] if item['language'] == 'systemverilog']
    if args.integrated:
        from .source_layout import integrated_source_paths
        expected_sv = ['sv/' + path for path in integrated_source_paths(
            proof['context']['sources'], compilation_unit=options['sv_compilation_unit'])]
    else:
        expected_sv = ['mirrors.sv']
    if sv != expected_sv:
        raise ValueError('export layout changed during cache observation')
    files = {manifest, evidence, artifact, root / 'python/.svx-generated-python.json'}
    if args.integrated:
        files.add(root / 'sv/.svx-generated-sv.json')
    for item in inventory['artifacts']:
        path = _safe_output(root, item['path'])
        if file_digest(path) != item['sha256']:
            raise ValueError('generated output changed during cache observation')
        files.add(path)
    return [{'path': path.relative_to(root).as_posix(), 'sha256': file_digest(path)} for path in sorted(files)]


def _load(path):
    try:
        if path.is_symlink():
            return None
        data = json.loads(path.read_text(encoding='utf-8'))
        if (set(data) != {'schema_uri', 'request', 'selection', 'outputs', 'summary', 'sha256'}
                or data['schema_uri'] != SCHEMA or not isinstance(data['summary'], str)
                or data['sha256'] != _digest({key: value for key, value in data.items() if key != 'sha256'})):
            return None
        return data
    except (OSError, ValueError, TypeError, KeyError):
        return None


def run_incremental_export(args, out, execute):
    """Reuse only a complete unchanged direct-SV export, with two fresh checks."""
    if args.python_module or args.sv_declarations or args.python_source:
        print('Incremental: unavailable for executable Python/explicit declaration inputs; running full export', file=out)
        return execute(args, out)
    if not any((args.sv_class, args.sv_package, args.sv_type, args.sv_constant, args.sv_callable)):
        return execute(args, out)
    root = Path(args.out)
    cache = root / '.svx-export-cache.json'
    try:
        prepared, options, request = _prepare(args)
    except (ImportError, OSError):
        print('Incremental: framework fingerprint unavailable; running full export', file=out)
        return execute(args, out)
    source_options = _source_options(options)
    with _selection_scope(prepared):
        context = selection_context(prepared.sv_source, **source_options)
        previous = None if args.refresh_cache else _load(cache)
        reason = 'forced refresh' if args.refresh_cache else 'no compatible cache'
        if previous is not None:
            if previous['request'] != request:
                reason = 'request, build configuration or framework changed'
            elif not validate_selection(previous['selection'], context):
                reason = 'source content or include/library selection changed'
            elif not _outputs_match(root, previous['outputs']):
                reason = 'generated outputs changed'
            elif (validate_selection(previous['selection'], context)
                  and _outputs_match(root, previous['outputs']) and _prepare(args)[2] == request):
                print('Incremental: reused verified export; 0 SV source parses', file=out)
                print(previous['summary'], end='', file=out)
                return 0
            else:
                reason = 'inputs or outputs changed during verification'
    print('Incremental: full export; ' + reason, file=out)
    stream = StringIO()
    status = execute(args, stream)
    summary = stream.getvalue()
    print(summary, end='', file=out)
    if args.check:
        return status
    try:
        with _selection_scope(prepared):
            proof = capture_selection(prepared.sv_source, **source_options)
            if proof is None:
                print('Incremental: cache not saved; source lookup is not replayable', file=out)
                return status
            outputs = _snapshot(root, args, options, proof)
            if (_prepare(args)[2] != request or not validate_selection(proof, context)
                    or not _outputs_match(root, outputs)):
                raise ValueError('inputs or outputs changed before cache publication')
        if cache.is_symlink():
            raise ValueError('cache path is a symlink')
        if cache.exists():
            owner = json.loads(cache.read_text(encoding='utf-8'))
            if not isinstance(owner, dict) or owner.get('schema_uri') != SCHEMA:
                raise ValueError('existing cache path is not owned by SVX')
        from .cli import _protect_generation_inputs
        from .inheritance import write_text_atomic
        _protect_generation_inputs([cache], [*(Path(item['path']) for item in proof['files']),
                                            *prepared._sv_build_configuration.inputs,
                                            *(root / item['path'] for item in outputs)])
        entry = {'schema_uri': SCHEMA, 'request': request, 'selection': proof,
                 'outputs': outputs, 'summary': summary}
        entry['sha256'] = _digest(entry)
        write_text_atomic(cache, json.dumps(entry, indent=2, sort_keys=True) + '\n')
    except (OSError, ValueError, TypeError, KeyError, SVXInheritanceError) as error:
        print(f'Incremental: cache not saved; {error}', file=out)
    return status
