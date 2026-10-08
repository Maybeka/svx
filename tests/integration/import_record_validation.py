"""Validate generated-input metadata through the public CLI."""

from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from svx.cli import main
from svx.errors import SVXInheritanceError
from tests.integration.sv_field_mirror_schema import manifest_data


def snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
            for path in root.rglob('*') if path.is_file()}


def run():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps(manifest_data()))
        artifact = root / 'artifacts.json'
        args = ['inheritance-gen', '--manifest', str(manifest), '--python-out', str(root / 'python'),
                '--sv-out', str(root / 'mirrors.sv'), '--artifact-manifest', str(artifact)]
        main(args, StringIO())
        valid = artifact.read_text()
        target = root / 'helper.py'
        target.write_text('# source\n')
        (root / 'alias.py').symlink_to(target)
        cases = [
            [{'path': 'helper.py', 'sha256': ''}],
            [{'path': 'helper.py', 'sha256': 'z' * 64}],
            [{'path': str(target), 'sha256': 'a' * 64}],
            [{'path': './helper.py', 'sha256': 'a' * 64}],
            [{'path': 'helper.py', 'sha256': 'a' * 64}] * 2,
            [{'path': name, 'sha256': 'a' * 64} for name in ('helper.py', 'alias.py')],
        ]
        for records in cases:
            metadata = json.loads(valid)
            metadata['generation_inputs']['python_imports'] = records
            artifact.write_text(json.dumps(metadata))
            before = snapshot(root)
            for flags in ([], ['--check']):
                try:
                    main(args + flags, StringIO())
                except SVXInheritanceError as error:
                    assert 'automatic Python input records' in str(error), error
                else:
                    raise AssertionError('damaged import records accepted')
                assert snapshot(root) == before
        artifact.write_text(valid)
        main(args + ['--check'], StringIO())
    print('IMPORT_RECORD_VALIDATION_PASS')


if __name__ == '__main__':
    run()
