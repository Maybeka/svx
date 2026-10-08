"""Verify discovery publication rollback using real file operations."""

import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from svx.cli import main
from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION
from tests.integration.sv_field_mirror_schema import manifest_data


def snapshot(root):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino, path.stat().st_mode)
            for path in root.rglob('*') if path.is_file()}


def run(directory):
    for existing in (False, True):
        points = ['staging', 'publish_before', 'publish_after']
        if existing:
            points.extend(['backup_before', 'backup_after'])
        for point in points:
            with TemporaryDirectory(dir=directory) as temporary:
                root = Path(temporary)
                declarations = root / 'declarations.json'
                data = {'schema_uri': SV_DECLARATION_SCHEMA_URI,
                        'schema_version': SV_DECLARATION_SCHEMA_VERSION,
                        'classes': [manifest_data()['classes'][0]]}
                declarations.write_text(json.dumps(data))
                target = root / 'manifest.json'
                args = ['inheritance-manifest', '--sv-declarations', str(declarations),
                        '--out', str(target)]
                if existing:
                    assert main(args, out=io.StringIO()) == 0
                    data['classes'][0]['canonical_id'] += 'Changed'
                    data['classes'][0]['symbol'] += 'Changed'
                    for method in data['classes'][0]['methods']:
                        method['canonical_id'] = data['classes'][0]['canonical_id'] + '#' + method['name']
                    declarations.write_text(json.dumps(data))
                before = snapshot(root)
                original_replace, original_sync = Path.replace, os.fsync
                sync_calls = 0

                def failing_sync(descriptor):
                    nonlocal sync_calls
                    sync_calls += 1
                    if point == 'staging' and sync_calls == 2:
                        raise OSError('injected staging failure')
                    return original_sync(descriptor)

                def failing_replace(source, destination):
                    destination = Path(destination)
                    publish = source.name.endswith('.tmp') and destination == target
                    backup = source == target and destination.name.endswith('.bak')
                    if (publish and point.startswith('publish')) or (backup and point.startswith('backup')):
                        if point.endswith('after'):
                            original_replace(source, destination)
                        raise OSError('injected publication failure')
                    return original_replace(source, destination)

                with patch.object(Path, 'replace', failing_replace), patch.object(os, 'fsync', failing_sync):
                    try:
                        main(args, out=io.StringIO())
                    except OSError as error:
                        assert 'injected' in str(error), error
                    else:
                        raise AssertionError('publication failure was not triggered')
                    assert snapshot(root) == before
                assert main(args, out=io.StringIO()) == 0
                complete = snapshot(root)
                assert main(args + ['--check'], out=io.StringIO()) == 0
                assert main(args, out=io.StringIO()) == 0
                assert snapshot(root) == complete
            print(f'DISCOVERY_PUBLICATION_CASE_PASS existing={existing} point={point}', flush=True)
    print('DISCOVERY_PUBLICATION_PASS', flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    run(args.directory.resolve())
