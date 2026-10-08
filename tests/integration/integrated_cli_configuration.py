"""Check invalid generator options without requiring a source parser."""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from svx.cli import main


def run():
    cases = [
        (['--sv-out', 'a.sv', '--sv-integrated-dir', 'integrated'], 'only one'),
        (['--sv-stage-dir', 'stages', '--sv-integrated-dir', 'integrated'], 'only one'),
        (['--sv-integrated-dir', 'integrated'], 'requires --sv-source'),
        (['--sv-integrated-dir', 'integrated', '--sv-source', 'one.sv', '--sv-source', 'two.sv'],
         'require --sv-compilation-unit'),
        (['--check', '--sv-integrated-dir', 'integrated', '--sv-source', 'one.sv'],
         '--check requires'),
    ]
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'invalid.json'
        path.write_text('{invalid JSON')
        before = (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
        for options, expected in cases:
            try:
                main(['inheritance-gen', '--manifest', str(path), *options], StringIO())
            except SystemExit as error:
                assert expected in str(error), (expected, error)
            else:
                raise AssertionError('invalid configuration accepted')
            assert (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino) == before
            assert list(Path(directory).iterdir()) == [path]
    print('INTEGRATED_CLI_CONFIGURATION_PASS')


if __name__ == '__main__':
    run()
