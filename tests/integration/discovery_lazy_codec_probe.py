"""Exercise lazy cached-codec guards without a test-runner dependency."""

import builtins
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile

from svx.cli import main
from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION
from svx.discovery_provenance import validate_discovery_provenance
from svx.errors import SVXInheritanceError
if __package__:
    from .sv_field_mirror_schema import manifest_data
else:
    from sv_field_mirror_schema import manifest_data


def run(stage='discovery'):
    helper_name, factory_name = 'svx_lazy_probe_types', 'svx_lazy_probe_factory'
    assert helper_name not in sys.modules and factory_name not in sys.modules
    statements = (
        f'import {helper_name}; return {helper_name}.Codec()',
        f'from {helper_name} import Codec; return Codec()',
        f'import importlib; return importlib.import_module("{helper_name}").Codec()',
    )
    for changed in (False, True):
        for index, statement in enumerate(statements):
            with tempfile.TemporaryDirectory(prefix='svx-lazy-codec-') as directory:
                root = Path(directory)
                original_path = list(sys.path)
                original_hooks = (builtins.__import__, importlib.import_module)
                sys.path.insert(0, directory)
                helper = root / f'{helper_name}.py'
                helper.write_text('from svtypes import Int\nCodec = Int\n')
                (root / f'{factory_name}.py').write_text('def make():\n    ' + statement + '\n')
                declaration = manifest_data()['classes'][0]
                binding = declaration['fields'][0]['type']
                binding.pop('svtypes')
                binding['python'] = {'module': factory_name, 'symbol': 'make'}
                metadata = root / 'declarations.json'
                metadata.write_text(json.dumps({
                    'schema_uri': SV_DECLARATION_SCHEMA_URI,
                    'schema_version': SV_DECLARATION_SCHEMA_VERSION,
                    'classes': [declaration],
                } if stage == 'discovery' else dict(manifest_data(), classes=[declaration])))
                target = root / 'out' / 'manifest.json'
                args = ['inheritance-manifest', '--sv-declarations', str(metadata), '--out', str(target)]
                if stage == 'generation':
                    target = root / 'out' / 'artifacts.json'
                    args = ['inheritance-gen', '--manifest', str(metadata),
                            '--python-out', str(target.parent / 'python'),
                            '--sv-out', str(target.parent / 'mirrors.sv'),
                            '--artifact-manifest', str(target)]
                try:
                    importlib.import_module(helper_name)
                    if changed:
                        helper.write_text('from svtypes import Bit\nCodec = Bit[16]\n')
                    try:
                        main(args, out=io.StringIO())
                    except SVXInheritanceError as error:
                        assert f'dependency is cached without current {stage} evidence' in str(error)
                    else:
                        raise AssertionError('cached lazy helper published output')
                    assert not target.parent.exists()
                    assert (builtins.__import__, importlib.import_module) == original_hooks
                    for name in (helper_name, factory_name):
                        sys.modules.pop(name, None)
                    helper.write_text('from svtypes import Int\nCodec = Int\n')
                    assert main(args, out=io.StringIO()) == 0
                    if stage == 'discovery':
                        assert helper.resolve() in validate_discovery_provenance(json.loads(target.read_text()), target)
                    else:
                        imports = json.loads(target.read_text())['generation_inputs']['python_imports']
                        assert any((target.parent / item['path']).resolve() == helper.resolve()
                                   for item in imports)
                    before = {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
                              for path in target.parent.rglob('*') if path.is_file()}
                    assert main(args + ['--check'], out=io.StringIO()) == 0
                    assert main(args, out=io.StringIO()) == 0
                    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
                                      for path in target.parent.rglob('*') if path.is_file()}
                    print(f'LAZY_CODEC_{stage.upper()}_CASE_PASS changed={changed} import={index}', flush=True)
                finally:
                    sys.path[:] = original_path
                    for name in (helper_name, factory_name):
                        sys.modules.pop(name, None)
                    assert (builtins.__import__, importlib.import_module) == original_hooks
    print(f'LAZY_CODEC_{stage.upper()}_PASS', flush=True)


if __name__ == '__main__':
    run()
    run('generation')
