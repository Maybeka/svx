import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from svx.cli import main
from svx.declarations import manifest_from_declarations
from tests.python.test_sv_constant_exports import import_generated

pytest.importorskip('pyslang')

SOURCE = Path(__file__).parents[2] / 'examples/sv_export/generic_values.sv'
PACKAGE = 'generic_class_constants_pkg'


def export(tmp_path, *selectors):
    output = tmp_path / 'generated'
    args = ['export', '--sv-source', str(SOURCE), '--out', str(output), *selectors]
    assert main(args, out=io.StringIO()) == 0
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in output.rglob('*') if path.is_file()}
    assert main([*args, '--check'], out=io.StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in output.rglob('*') if path.is_file()}
    return output, json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))


def test_closed_class_alias_snapshots_bind_distinct_native_specializations(tmp_path):
    output, data = export(tmp_path, '--constant', PACKAGE + '::Narrow::*', PACKAGE + '::Wide::*')
    assert data['classes'] == []
    assert all('::Config::' not in item['symbol'] for item in data.get('value_types', []))
    import_generated(output, '''from svx_mirror.generic_class_constants_pkg import Narrow, Wide
import svtypes, sys
assert Narrow.WIDTH == 9 and Narrow.COUNT == 10
assert Wide.WIDTH == 70 and Wide.COUNT == 71
assert Narrow.DEFAULT_MODE == Narrow.Mode.READY
assert Wide.DEFAULT_MODE == Wide.Mode.READY
assert Narrow.Mode is not Wide.Mode
assert svtypes.schema_descriptor(Narrow.Mode).to_dict()['schema']['width'] == 9
assert svtypes.schema_descriptor(Wide.Mode).to_dict()['schema']['width'] == 70
assert str(Narrow.DEFAULT_PACKET.data.value) == 'x' * 9
assert str(Wide.DEFAULT_PACKET.data.value) == 'x' * 70
assert Narrow.DEFAULT_ITEM.code.value == Wide.DEFAULT_ITEM.code.value == 0
assert 'svx' not in sys.modules
''')


def test_named_values_of_closed_aliases_are_selectable_and_share_equivalent_alias_identity(tmp_path):
    output, data = export(tmp_path, '--type', PACKAGE + '::Narrow::Mode',
                          PACKAGE + '::Same::Mode', PACKAGE + '::Narrow::Packet',
                          PACKAGE + '::Same::Packet', PACKAGE + '::Wide::Packet')
    assert data['classes'] == []
    import_generated(output, '''from svx_mirror.generic_class_constants_pkg import Narrow, Same, Wide
import svtypes
assert Narrow.Mode is Same.Mode
assert Narrow.Packet is Same.Packet
assert svtypes.schema_descriptor(Narrow.Mode).to_dict()['schema']['width'] == 9
packet = Wide.Packet()
assert svtypes.schema_descriptor(packet.data).to_dict()['schema']['width'] == 70
assert svtypes.schema_descriptor(packet.mode).to_dict()['schema']['width'] == 70
''')


@pytest.mark.parametrize('selector', ['WIDTH', 'COUNT', 'DEFAULT_MODE', 'DEFAULT_PACKET', 'DEFAULT_ITEM'])
def test_inherited_constant_selector_uses_resolved_base_specialization(tmp_path, selector):
    output, data = export(tmp_path, '--constant', PACKAGE + '::Child::' + selector)
    assert [item['symbol'] for item in data['constants']] == [PACKAGE + '::Child::' + selector]
    expected = {'WIDTH': 'assert Child.WIDTH == 9', 'COUNT': 'assert Child.COUNT == 10',
                'DEFAULT_MODE': 'assert Child.DEFAULT_MODE == Child.Mode.READY',
                'DEFAULT_PACKET': "assert str(Child.DEFAULT_PACKET.data.value) == 'x' * 9",
                'DEFAULT_ITEM': 'assert Child.DEFAULT_ITEM.code.value == 0'}
    import_generated(output, 'from svx_mirror.generic_class_constants_pkg import Child\n' + expected[selector])


def test_plain_inherited_constant_selection_does_not_create_base_mirror(tmp_path):
    source = Path(__file__).parents[1] / 'integration/class_constants.sv'
    model = manifest_from_declarations(sv_source_files=[source],
        sv_constant_targets=['class_constants_pkg::Derived::WIDTH'])
    assert not model.classes
    assert [item.symbol for item in model.constants] == ['class_constants_pkg::Derived::WIDTH']


def test_complete_sv_defaults_are_resolved_without_an_extra_alias(tmp_path):
    output, data = export(tmp_path, '--constant', PACKAGE + '::Config::*')
    assert data['classes'] == []
    import_generated(output, '''from svx_mirror.generic_class_constants_pkg import Config
import svtypes
assert Config.WIDTH == 8 and Config.COUNT == 9
assert svtypes.schema_descriptor(Config.Mode).to_dict()['schema']['width'] == 8
assert str(Config.DEFAULT_PACKET.data.value) == 'x' * 8
assert Config.DEFAULT_ITEM == 0
''')


def test_missing_required_parameter_is_not_filled_with_a_guessed_type(tmp_path):
    from svx.errors import SVXInheritanceError
    source = tmp_path / 'required.sv'
    source.write_text('package p; class G#(type T);localparam int COUNT=7;endclass '
                      'typedef G#(bit[3:0]) Bound;endpackage', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='matched no package parameter/localparam'):
        manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['p::G::COUNT'])
    model = manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['p::Bound::COUNT'])
    assert not model.classes and [item.symbol for item in model.constants] == ['p::Bound::COUNT']


def test_package_function_only_export_keeps_closed_types_without_class_factories(tmp_path):
    output, data = export(tmp_path, '--callable', *(PACKAGE + '::' + name
        for name in ('narrow_echo', 'wide_packet', 'wide_echo')))
    assert data['classes'] == []
    assert 'constants' not in data
    assert all('::Config::' not in item['symbol'] for item in data['value_types'])
    code = '''from svx_mirror.generic_class_constants_pkg import Narrow, Wide, narrow_echo, wide_packet, wide_echo
import svtypes
assert not isinstance(Narrow, type) and not isinstance(Wide, type)
assert callable(narrow_echo) and callable(wide_packet) and callable(wide_echo)
assert svtypes.schema_descriptor(Narrow.Mode).to_dict()['schema']['width'] == 9
assert svtypes.schema_descriptor(Wide.Packet().data).to_dict()['schema']['width'] == 70
'''
    result = subprocess.run([sys.executable, '-B', '-c', code],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
            str(output / 'python'), str(SOURCE.parents[2] / 'python'),
            str(SOURCE.parents[2].parent / 'svtypes/python')])),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_default_owner_metadata_replays_without_inferring_its_native_spelling():
    from svx.declarations import manifest_dict
    from svx.inheritance import emit_sv_mirrors, parse_manifest
    data = manifest_dict(manifest_from_declarations(sv_source_files=[SOURCE],
        sv_callable_targets=[PACKAGE + '::default_packet']))
    assert data['schema_version'] == '2.7.0'
    assert data['classes'] == []
    owner = PACKAGE + '::Config'
    declarations = {item['symbol']: item for item in data['value_types']}
    assert declarations[owner + '::Mode']['default_class_owners'] == [owner]
    assert declarations[owner + '::Packet']['default_class_owners'] == [owner]
    model = parse_manifest(data)
    assert manifest_dict(model) == data
    assert owner + '#()::Mode' in emit_sv_mirrors(model)


@pytest.mark.parametrize('owners', [None, {}, [PACKAGE], [PACKAGE + '::Wide'],
    [PACKAGE + '::Config', PACKAGE + '::Config'], [PACKAGE + '::Config#()'],
    [PACKAGE + '::Config;bad']])
def test_default_owner_metadata_rejects_non_structural_or_unrelated_names(owners):
    from svx.declarations import manifest_dict
    from svx.inheritance import parse_manifest
    from svx.errors import SVXInheritanceError
    data = manifest_dict(manifest_from_declarations(sv_source_files=[SOURCE],
        sv_constant_targets=[PACKAGE + '::Config::WIDTH']))
    data['constants'][0]['default_class_owners'] = owners
    with pytest.raises(SVXInheritanceError, match='invalid default class owners'):
        parse_manifest(data)


@pytest.mark.parametrize('with_constants', [False, True])
def test_closed_alias_mirrors_publish_required_types_at_each_public_owner(tmp_path, with_constants):
    selectors = ['--class', *(PACKAGE + '::' + name for name in ('Child', 'Narrow', 'Same', 'Wide'))]
    if with_constants:
        selectors += ['--constant', PACKAGE + '::Narrow::*', PACKAGE + '::Wide::*', PACKAGE + '::Child::WIDTH']
    output, data = export(tmp_path, *selectors)
    assert all('::Config::' not in item['symbol'] for item in data.get('value_types', []))
    assert {item['symbol'] for item in data['classes']} == {PACKAGE + '::' + name for name in ('Child', 'Narrow', 'Same', 'Wide')}
    for cls in data['classes']:
        for method in cls['methods']:
            for binding in [method['return_type'], *(arg['type'] for arg in method['parameters'])]:
                if isinstance(binding, dict):
                    assert '::Config::' not in binding['sv']
    code = '''from svx_mirror.generic_class_constants_pkg import Child, Narrow, Same, Wide
from svx_mirror.generic_constants_types_pkg import Item
import svtypes
assert issubclass(Child, Narrow)
assert Narrow.Mode is Same.Mode is Child.Mode
assert Narrow.T is Same.T is Wide.T is Item
assert Narrow.Mode is not Wide.Mode
assert svtypes.schema_descriptor(Narrow.Mode).to_dict()['schema']['width'] == 9
assert svtypes.schema_descriptor(Wide.Mode).to_dict()['schema']['width'] == 70
'''
    result = subprocess.run([sys.executable, '-B', '-c', code],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
            str(output / 'python'), str(SOURCE.parents[2] / 'python'),
            str(SOURCE.parents[2].parent / 'svtypes/python')])),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
