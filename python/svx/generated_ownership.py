"""Generation-only protection for manually edited executable artifacts."""
import hashlib
import json
from pathlib import Path

from .errors import SVXInheritanceError


def baseline_name(inventory):
    return inventory+'.sha256.json'


def baseline_text(sources):
    return json.dumps({'schema': 'svx-generated-baseline/v1',
        'files': {str(path): hashlib.sha256(text.encode('utf-8')).hexdigest()
                  for path, text in sorted(sources.items(), key=lambda item: str(item[0]))}},
        indent=2)+'\n'


def protect_baseline(output_dir, inventory, sources, obsolete, *, overwrite=False):
    path = Path(output_dir)/baseline_name(inventory)
    if not path.exists():
        if not overwrite:
            for name, text in sources.items():
                target = Path(output_dir)/name
                if target.is_file() and target.read_bytes() != text.encode('utf-8'):
                    raise SVXInheritanceError(
                        f'cannot verify existing generated artifact without a recorded snapshot: {target}; '
                        'preserve the patch or use a new output directory; '
                        '--overwrite-generated explicitly permits replacement')
            for target in obsolete:
                if Path(target).is_file():
                    raise SVXInheritanceError(
                        f'cannot retire generated artifact without a recorded snapshot: {target}; '
                        'preserve the patch or use a new output directory; '
                        '--overwrite-generated explicitly permits replacement')
        return
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or set(raw) != {'schema', 'files'} or raw['schema'] != 'svx-generated-baseline/v1':
            raise ValueError('unrecognized schema')
        files = raw['files']
        if not isinstance(files, dict) or any(not isinstance(name, str) or not isinstance(digest, str)
            or len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest)
            for name, digest in files.items()):
            raise ValueError('invalid file digest table')
    except (OSError, ValueError) as error:
        raise SVXInheritanceError(f'invalid generated baseline {path}: {error}') from error
    previous = {'artifacts': [{'path': name, 'sha256': digest} for name, digest in files.items()]}
    expected = {Path(output_dir)/name: text for name, text in sources.items()}
    protect_manual_edits(previous, path, [*expected, *obsolete], overwrite=overwrite, expected_sources=expected)


def protect_manual_edits(previous, manifest_path, managed_paths, *, overwrite=False, expected_sources=None):
    if overwrite or previous is None:
        return
    managed = {Path(path).resolve() for path in managed_paths}
    expected = {Path(path).resolve(): text.encode('utf-8') for path, text in (expected_sources or {}).items()}
    root = Path(manifest_path).resolve().parent
    for entry in previous.get('artifacts', ()):
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            continue
        path = (root/entry['path']).resolve()
        if path not in managed or not path.is_file():
            continue
        digest = entry.get('sha256')
        current = path.read_bytes()
        if current == expected.get(path):
            continue  # Also permits retry after interrupted generated publication.
        if isinstance(digest, str) and hashlib.sha256(current).hexdigest() != digest:
            raise SVXInheritanceError(
                f'generated artifact differs from its recorded snapshot (possible manual edits): {path}; preserve the patch or use a new '
                'output directory; --overwrite-generated explicitly permits replacement')
