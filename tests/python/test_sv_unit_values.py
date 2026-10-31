import io
import json

import pytest

from svx.cli import main
from svx.errors import SVXInheritanceError
from svx.inheritance import parse_manifest
from test_sv_nested_classes import subprocess_import

pytest.importorskip('pyslang')


@pytest.fixture
def project(tmp_path):
    source = tmp_path / 'values.sv'
    source.write_text('''typedef enum bit[3:0] {IDLE=0, ACTIVE=5} Mode;
typedef struct packed {Mode mode;logic[3:0] flags;} Packet;
typedef Packet Alias;
typedef bit[12:0] Word;
typedef Mode Modes[];
localparam Mode START=ACTIVE;
localparam Packet INITIAL={ACTIVE,4'b10xz};
localparam int DEPTH=9;
class Holder;
typedef enum bit[1:0] {OFF=0, ON=1} State;
typedef struct packed {State state;bit[7:0] data;} Payload;
endclass
package __unit__;
typedef enum bit[3:0] {OTHER=7} Mode;
class Driver;function int get();return 3;endfunction endclass
endpackage
''', encoding='utf-8')
    return source


def run(args):
    output = io.StringIO()
    assert main(args, out=output) == 0
    return output.getvalue()


def test_unit_values_preserve_native_identity_and_public_svtypes(project, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--type', '$unit::*', '--constant', '$unit::*',
            '--sv-source', str(project), '--out', str(output)]
    message = run(args)
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert data['schema_version'] == '2.4.0' and data['classes'] == []
    assert {item['symbol'] for item in data['value_types']} >= {'$unit::Mode', '$unit::Packet', '$unit::Holder::Payload'}
    assert all(item['source_scope'] == {'kind': 'compilation_unit', 'index': 0}
               for item in (*data['value_types'], *data['constants']))
    assert 'from svx_mirror_unit.unit_0 import Mode' in message
    assert 'systemverilog_startup' not in json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    subprocess_import(output, '''import svtypes
from svx_mirror_unit.unit_0 import Mode, Packet, Alias, Word, Modes, START, INITIAL, DEPTH, Holder
assert Mode.ACTIVE == START == 5 and DEPTH == 9
assert Mode.__module__ == 'svx_mirror_unit.unit_0'
assert svtypes.schema_descriptor(Mode).to_dict()['schema']['type_name'] == 'svx_mirror_unit.unit_0.Mode'
assert INITIAL.mode.value == 5
assert INITIAL.flags.value == svtypes.LogicValue.from_string('10xz')
assert Word().width == 13
assert Holder.State.ON == 1 and Holder.Payload.__qualname__ == 'Holder.Payload'
modes = Modes()
modes.value = [Mode.IDLE,Mode.ACTIVE]
assert modes.to_bytes()
assert Alias is Packet
assert 'svx' not in __import__('sys').modules
''')
    run(args + ['--check'])


def test_unit_and_real_package_namespace_do_not_collide(project, tmp_path):
    output = tmp_path / 'generated'
    run(['export', '--type', '$unit::Mode', '__unit__::Mode', '--sv-source', str(project), '--out', str(output)])
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Mode
from svx_mirror.__unit__ import Mode as PackageMode
assert Mode.ACTIVE == 5 and PackageMode.OTHER == 7
assert Mode is not PackageMode
''')


def test_unit_snapshots_do_not_leak_into_package_call_records(project, tmp_path):
    output = tmp_path / 'generated'
    run(['export', '--class', '__unit__::Driver', '--type', '$unit::Packet',
         '--sv-source', str(project), '--out', str(output)])
    text = (output / 'mirrors.sv').read_text(encoding='utf-8')
    assert 'import $unit::*' not in text and 'typedef $unit::' not in text
    assert 'extends __unit__::Driver' in text
    subprocess_import(output, 'from svx_mirror_unit.unit_0 import Packet\nfrom svx_mirror.__unit__ import Driver\n')


def test_unit_lookup_is_ambiguous_without_owner_index(tmp_path):
    first, second = tmp_path / 'one.sv', tmp_path / 'two.sv'
    first.write_text('typedef bit[4:0] Word;localparam int DEPTH=5;', encoding='utf-8')
    second.write_text('typedef bit[12:0] Word;localparam int DEPTH=13;', encoding='utf-8')
    context = ['--sv-source', str(first), '--sv-source', str(second)]
    with pytest.raises(SVXInheritanceError, match=r'ambiguous SV type.*\$unit\[0\].*\$unit\[1\]'):
        run(['export', '--type', '$unit::Word', *context, '--out', str(tmp_path / 'ambiguous')])
    output = tmp_path / 'chosen'
    run(['export', '--type', '$unit[1]::Word', '--constant', '$unit[1]::DEPTH', *context, '--out', str(output)])
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert data['value_types'][0]['source_scope']['index'] == 1
    subprocess_import(output, 'from svx_mirror_unit.unit_1 import Word, DEPTH\nassert Word().width == DEPTH == 13\n')


def test_distinct_unit_owners_are_not_silently_merged(tmp_path):
    first, second = tmp_path / 'one.sv', tmp_path / 'two.sv'
    first.write_text('typedef bit[4:0] First;', encoding='utf-8')
    second.write_text('typedef bit[12:0] Second;', encoding='utf-8')
    output = tmp_path / 'generated'
    run(['export', '--type', 'First', 'Second', '--sv-source', str(first), '--sv-source', str(second),
         '--out', str(output)])
    subprocess_import(output, 'from svx_mirror_unit.unit_0 import First\n'
        'from svx_mirror_unit.unit_1 import Second\nassert First().width == 5 and Second().width == 13\n')


def test_shared_unit_dependencies_and_incremental_check(project, tmp_path, monkeypatch):
    import svx.sv_scan as scanner
    prefix = tmp_path / 'prefix.sv'
    prefix.write_text('`define WIDTH 13\n', encoding='utf-8')
    second = tmp_path / 'aliases.sv'
    second.write_text('typedef bit[`WIDTH-1:0] Word;', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--type', 'Word', '--sv-source', str(prefix), '--sv-source', str(second),
            '--sv-compilation-unit', '--incremental', '--out', str(output)]
    run(args)
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in output.rglob('*') if path.is_file()}
    monkeypatch.setattr(scanner, '_parse_source_batch', lambda *a, **kw: pytest.fail('warm parse'))
    assert 'reused verified export' in run(args + ['--check'])
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in output.rglob('*') if path.is_file()}


def test_same_named_values_from_two_units_keep_distinct_types(tmp_path):
    sources = [tmp_path / 'first.sv', tmp_path / 'second.sv']
    for source, value in zip(sources, (1, 9)):
        source.write_text(f'typedef enum bit[3:0] {{ACTIVE={value}}} Mode;localparam Mode START=ACTIVE;', encoding='utf-8')
    output = tmp_path / 'generated'
    run(['export', '--type', '$unit::*', '--constant', '$unit::*',
         '--sv-source', str(sources[0]), '--sv-source', str(sources[1]), '--out', str(output)])
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['value_types']] == ['$unit::Mode', '$unit::Mode']
    assert {item['source_scope']['index'] for item in data['value_types']} == {0, 1}
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Mode as First, START as A
from svx_mirror_unit.unit_1 import Mode as Second, START as B
assert First is not Second and First.ACTIVE == A == 1 and Second.ACTIVE == B == 9
''')


def test_unit_named_runtime_contract_rejects_missing_owner_local_records(project, tmp_path):
    import svtypes
    from svx.value_exports import parse_value_exports, value_modules
    output = tmp_path / 'generated'
    run(['export', '--type', '$unit::Mode', '--sv-source', str(project), '--out', str(output)])
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    data.pop('discovery_provenance')
    with value_modules(parse_value_exports(data['value_types'])) as modules:
        annotation = modules.annotations['$unit[0]::Mode']
        encoding = svtypes.encoding_descriptor(annotation).to_dict()
    binding = {'svtypes': data['value_types'][0]['svtypes'], 'encoding_descriptor': encoding,
               'unified_type_name': encoding['unified_type_name'], 'sv': '$unit::Mode',
               'sv_packer': 'svtypes_pkg::bit_packer#(bit[3:0])'}
    data['classes'] = [{'canonical_id': 'sv://p/Driver', 'language': 'sv', 'symbol': 'p::Driver',
        'methods': [{'canonical_id': 'sv://p/Driver#check', 'name': 'check', 'timing': 'function',
                     'parameters': [{'name': 'mode', 'direction': 'input', 'type': binding}],
                     'return_type': 'void', 'virtual': True}]}]
    with pytest.raises(SVXInheritanceError, match='owner-local call records'):
        parse_manifest(data)


def test_parameterized_unit_named_alias_does_not_invent_package(tmp_path):
    source = tmp_path / 'generic.sv'
    source.write_text('class G#(int W=4);typedef enum bit[W-1:0]{ACTIVE=2} Mode;endclass\n'
                      'typedef G#(8)::Mode Big;', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='specialization-aware ownership'):
        run(['export', '--type', 'Big', '--sv-source', str(source), '--out', str(tmp_path / 'generated')])


@pytest.mark.parametrize('scope', [None, {'kind': 'package', 'index': 0},
                                   {'kind': 'compilation_unit', 'index': True}])
def test_unit_scope_metadata_is_required_and_validated(project, tmp_path, scope):
    output = tmp_path / 'generated'
    run(['export', '--type', '$unit::Mode', '--sv-source', str(project), '--out', str(output)])
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    data.pop('discovery_provenance', None)
    item = data['value_types'][0]
    item.pop('source_scope')
    if scope is not None:
        item['source_scope'] = scope
    with pytest.raises(SVXInheritanceError, match='scope|package/type'):
        parse_manifest(data)
