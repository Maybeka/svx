import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import svtypes

from svx.cli import main

pytest.importorskip('pyslang')
SOURCE = Path(__file__).parents[1] / 'integration/enum_fixed_arrays.sv'


def import_mirrors(output, code):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(output / 'python'), str(SOURCE.parents[2] / 'python'),
        str(Path(svtypes.__file__).resolve().parents[1])]))
    result = subprocess.run([sys.executable, '-B', '-c', code], env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('package', [False, True])
@pytest.mark.parametrize('fields_only', [False, True])
def test_two_class_owned_enum_fixed_arrays(tmp_path, package, fields_only):
    source = SOURCE.with_name('class_enum_arrays.sv')
    output = tmp_path / 'generated'
    args = ['export', '--sv-source', str(source),
            *(['--package', 'class_enum_arrays_pkg'] if package else
              ['--class', 'class_enum_arrays_pkg::Driver']), '--out', str(output)]
    if fields_only:
        args += ['--member', 'first', 'second']
    assert main(args, out=io.StringIO()) == 0
    assert main([*args, '--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    fields = {field['name']: field['type'] for field in data['classes'][0]['fields']}
    assert fields['first']['unified_type_name'] != fields['second']['unified_type_name']
    assert fields['first']['svtypes']['args'][-1] == fields['second']['svtypes']['args'][-1] == 3
    text = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*')
                     if path.suffix in {'.sv', '.svh'})
    aliases = list(re.finditer(r'typedef (SVXScopedValue_\w+) (_svx__array_fixed3_enum\w*) \[3\];', text))
    if not fields_only:
        assert len(aliases) == 2 and aliases[0][2] != aliases[1][2]
    for alias in aliases:
        definition = re.search(r'typedef class_enum_arrays_pkg::Driver::\w+ ' + alias[1] + ';', text)
        assert definition is not None and definition.start() < alias.start()
    assert 'input first_t [3]' not in text and 'input second_t [3]' not in text
    import_mirrors(output, '''from svx_mirror.class_enum_arrays_pkg import Driver
import svtypes
assert Driver.first_t is not Driver.second_t
assert svtypes.unified_type_name(Driver.first_t) != svtypes.unified_type_name(Driver.second_t)
assert int(Driver.first_t.A_RUN) == 1 and int(Driver.second_t.B_RUN) == 2
''')


@pytest.mark.parametrize('package', [False, True])
@pytest.mark.parametrize('size', [3, 5])
def test_multiple_nominal_enum_fixed_arrays_keep_types_and_dimensions(tmp_path, package, size):
    output = tmp_path / 'generated'
    args = ['export', '--sv-source', str(SOURCE), '--sv-define', f'ENUM_FIXED_DEPTH={size}',
            *(['--package', 'enum_fixed_arrays_pkg'] if package else
              ['--class', 'enum_fixed_arrays_pkg::Driver']),
            '--exclude-member', 'enum_fixed_arrays_pkg::Base.ignored', '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main([*args, '--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    driver = next(item for item in data['classes'] if item['symbol'] == 'enum_fixed_arrays_pkg::Driver')
    fields = {field['name']: field['type'] for field in driver['fields']}
    assert fields['first']['svtypes']['args'][-1] == size
    assert fields['second']['svtypes']['args'][-1] == size
    assert fields['first']['unified_type_name'] != fields['second']['unified_type_name']
    assert fields['wide']['svtypes']['args'][-1] == 2
    import_mirrors(output, '''from svx_mirror.enum_fixed_arrays_pkg import first_t, second_t, wide_t, Bundle
import svtypes
assert first_t is not second_t
assert svtypes.unified_type_name(first_t) != svtypes.unified_type_name(second_t)
assert int(first_t.RUN) == int(second_t.RUN) == 1
assert int(wide_t.HIGH) == 257
assert svtypes.schema_descriptor(Bundle).to_dict()['schema']['kind'] == 'struct'
''')
