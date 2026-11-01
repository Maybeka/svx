import os
import json
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip('pyslang')


@pytest.mark.parametrize('source_first', [False, True])
@pytest.mark.parametrize('whole_package', [False, True])
def test_package_type_graph_with_alternating_and_native_families(tmp_path, source_first, whole_package):
    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    selection = (['--package', 'export_chain_pkg'] if whole_package else
                 ['--class', 'export_chain_pkg::C', 'export_chain_pkg::CLeaf'])
    arguments = [sys.executable, '-m', 'svx', 'export', '--integrated', *selection, '--python-module',
                 'tests.integration.package_export_alternating', '--sv-source',
                 str(root / 'tests/integration/package_export_alternating.sv'),
                 '--sv-include-dir', str(root), '--out', str(tmp_path)]
    result = subprocess.run(arguments, env=environment, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    artifact = json.loads((tmp_path / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['systemverilog_startup'] == 'svx_exports_pkg::initialize'
    program = f'''
from pathlib import Path
from svx import runtime
if {source_first!r}:
    import tests.integration.package_export_alternating
else:
    from svx_mirror.export_chain_pkg import CLeaf
runtime._load_artifact_manifest(Path({str(tmp_path / 'artifacts.json')!r}), runtime._read_svtypes_capabilities())
from tests.integration.package_export_alternating import B
from svx_mirror.export_chain_pkg import A, C, CLeaf
assert issubclass(B, A) and issubclass(C, B)
assert CLeaf.__bases__ == (C,)
namespace = {{}}
exec('from svx_mirror.export_chain_pkg import *', namespace)
assert namespace['CLeaf'] is CLeaf and namespace['C'] is C
if {whole_package!r}:
    from svx_mirror.export_chain_pkg import NativeBase, NativeDriver
    assert NativeDriver.__bases__ == (NativeBase,)
    assert namespace['NativeDriver'] is NativeDriver
'''
    environment['PYTHONPATH'] = os.pathsep.join([str(tmp_path / 'python'), *sys.path])
    imported = subprocess.run([sys.executable, '-c', program], env=environment,
                              text=True, capture_output=True, timeout=30)
    assert imported.returncode == 0, imported.stdout + imported.stderr
