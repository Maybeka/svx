"""Verify selected SV dependencies through the actual discovery and generator CLI."""

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from svx.cli import main
from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION
from svx.errors import SVXInheritanceError
from tests.integration.sv_field_mirror_schema import manifest_data
from tests.python.test_iterative_discovery_workflow import run_cli, snapshot


def selection_inputs(root, shared=False):
    first, second = root / 'first', root / 'second'
    first.mkdir()
    second.mkdir()
    source = root / 'source.sv'
    paths = [source]
    if shared:
        prefix = root / 'prefix.sv'
        prefix.write_text('`define HEADER "owner.svh"\n')
        source.write_text('`include `HEADER\n')
        paths.insert(0, prefix)
    else:
        source.write_text('`include "owner.svh"\n')
    text = ('package field_owner_pkg; class Base; int count; '
            'function int get_count(); return count; endfunction '
            'function void set_count(int value); count = value; endfunction '
            'endclass endpackage\n')
    (second / 'owner.svh').write_text(text)
    declarations = root / 'declarations.json'
    declarations.write_text(json.dumps({'schema_uri': SV_DECLARATION_SCHEMA_URI,
                                        'schema_version': SV_DECLARATION_SCHEMA_VERSION,
                                        'classes': [manifest_data()['classes'][0]]}))
    manifest = root / 'manifest.json'
    discovery = ['inheritance-manifest', '--sv-declarations', str(declarations)]
    for path in paths:
        discovery.extend(['--sv-source', str(path)])
    discovery.extend(['--sv-include-dir', str(first), '--sv-include-dir', str(second),
                      '--out', str(manifest)])
    if shared:
        discovery.append('--sv-compilation-unit')
    generate = ['inheritance-gen', '--manifest', str(manifest),
                '--python-out', str(root / 'generated' / 'python'),
                '--sv-out', str(root / 'generated' / 'mirrors.sv'),
                '--artifact-manifest', str(root / 'generated' / 'artifacts.json')]
    return discovery, generate, first, text


def run():
    import svx.inheritance

    for shared in (False, True):
        for changed in (False, True):
            with TemporaryDirectory() as directory:
                root = Path(directory)
                discovery, generate, first, text = selection_inputs(root, shared)
                result = run_cli(root, *discovery)
                assert result.returncode == 0, result.stderr
                assert main(generate, out=io.StringIO()) == 0
                complete = snapshot(root)
                for flags in (('--check',), ()):
                    result = run_cli(root, *discovery, *flags, preload=('pyslang',))
                    assert result.returncode == 0, result.stderr
                    assert snapshot(root) == complete
                before = snapshot(root / 'generated')
                (first / 'owner.svh').write_text(text + ('// preferred\n' if changed else ''))
                original = svx.inheritance._parse_class

                def forbidden(*args, **kwargs):
                    raise AssertionError('changed selection reached class parsing')

                svx.inheritance._parse_class = forbidden
                try:
                    for flags in ([], ['--check']):
                        try:
                            main(generate + flags, out=io.StringIO())
                        except SVXInheritanceError as error:
                            assert 'discovery dependency selection changed' in str(error), error
                            assert 'first/owner.svh' in str(error), error
                            assert 'second/owner.svh' in str(error), error
                        else:
                            raise AssertionError('changed discovery selection was accepted')
                        assert snapshot(root / 'generated') == before
                finally:
                    svx.inheritance._parse_class = original
                result = run_cli(root, *discovery)
                assert result.returncode == 0, result.stderr
                assert main(generate, out=io.StringIO()) == 0
                current = snapshot(root / 'generated')
                assert {name: value for name, value in current.items() if name != 'artifacts.json'} == {
                    name: value for name, value in before.items() if name != 'artifacts.json'}
                assert main(generate + ['--check'], out=io.StringIO()) == 0
            print(f'DISCOVERY_SELECTION_CASE_PASS shared={shared} changed={changed}', flush=True)
    print('DISCOVERY_SELECTION_PASS', flush=True)


if __name__ == '__main__':
    run()
