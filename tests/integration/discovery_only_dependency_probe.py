"""Verify discovery-only sources cannot leave an old contract certified."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.python.test_iterative_discovery_workflow import run_cli, snapshot


def run():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        helper = root / 'declaration_types.py'
        helper.write_text('import svtypes\nScalar = svtypes.Bit[8]\n')
        (root / 'declaration_owner.py').write_text('''import svtypes
import svx
from declaration_types import Scalar

@svx.inheritance_class(canonical_id="py://probe/Driver")
class Driver:
    @svx.inheritance_method
    def check(self, value: Scalar) -> svx.Function[svtypes.Int]:
        return int(value)
''')
        output = root / 'generated'
        output.mkdir()
        manifest = output / 'manifest.json'
        discover = ('inheritance-manifest', '--python-module', 'declaration_owner', '--out', str(manifest))
        generate = ('inheritance-gen', '--manifest', str(manifest),
                    '--python-out', str(output / 'python'), '--sv-out', str(output / 'mirrors.sv'),
                    '--artifact-manifest', str(output / 'artifacts.json'))
        for command in (discover, generate):
            result = run_cli(root, *command)
            assert result.returncode == 0, result.stderr
        before = snapshot(output)
        helper.write_text('import svtypes\nScalar = svtypes.Bit[16]\n')
        result = run_cli(root, *generate, '--check')
        assert result.returncode != 0 and 'discovery source changed' in result.stderr, result.stderr
        result = run_cli(root, *generate)
        assert result.returncode != 0 and 'discovery source changed' in result.stderr, result.stderr
        result = run_cli(root, *discover, '--check')
        assert result.returncode != 0 and 'manifest is stale' in result.stderr, result.stderr
        assert snapshot(output) == before
        original = json.loads(manifest.read_text())
        result = run_cli(root, *discover)
        assert result.returncode == 0, result.stderr
        assert json.loads(manifest.read_text()) != original
        result = run_cli(root, *generate, '--check')
        assert result.returncode != 0 and 'stale' in result.stderr, result.stderr
        result = run_cli(root, *generate)
        assert result.returncode == 0, result.stderr
        assert run_cli(root, *generate, '--check').returncode == 0
    print('DISCOVERY_ONLY_DEPENDENCY_PASS')


if __name__ == '__main__':
    run()
