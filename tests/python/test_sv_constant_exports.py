import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import svtypes

from svx.cli import main
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import parse_manifest
from svx.value_exports import value_modules

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'constants.sv'
    path.write_text('''package dependency;
  parameter int DEPTH=6;
endpackage
package values;
  import dependency::*;
  typedef enum bit [3:0] {IDLE=0, RUN=5} State;
  typedef struct packed {bit [7:0] tag; State state; logic [3:0] flags;} Packet;
  localparam int COUNT=DEPTH*3;
  parameter int NEGATIVE=-4;
  parameter string LABEL="hello";
  parameter real GAIN=2.5;
  localparam logic [3:0] FLAGS=4'b10xz;
  localparam State DEFAULT_STATE=RUN;
  localparam Packet DEFAULT_PACKET='{tag:8'h81, state:RUN, flags:4'bxz10};
  localparam int TABLE[3]='{1, -2, 3};
  localparam int bytes=4;
  localparam int _svx_builtins=7;
  const int RUNTIME_VALUE=9;
endpackage''', encoding='utf-8')
    return path


def import_generated(output, code):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(output / 'python'), str(Path(svtypes.__file__).resolve().parents[1])]))
    result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_package_constants_are_typed_snapshots_without_native_runtime(source, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--package', 'values', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert data['schema_version'] == '2.2.0' and data['classes'] == []
    assert len(data['constants']) == 10
    assert all(item['symbol'].startswith('values::') for item in data['constants'])
    assert main(args + ['--check'], out=io.StringIO()) == 0
    import_generated(output, '''from svx_mirror.values import *
assert COUNT == 18 and NEGATIVE == -4 and LABEL == 'hello' and GAIN == 2.5
assert str(FLAGS) == '10xz'
assert DEFAULT_STATE == State.RUN
assert DEFAULT_PACKET.tag.value == 0x81
assert DEFAULT_PACKET.state.value == State.RUN
assert str(DEFAULT_PACKET.flags.value) == 'xz10'
assert TABLE == [1, -2, 3]
assert bytes == 4 and _svx_builtins == 7
import sys
assert 'svx' not in sys.modules
assert 'RUNTIME_VALUE' not in globals()
'''.replace('from svx_mirror.values import *',
            'from svx_mirror.values import *\nfrom svx_mirror.values import _svx_builtins'))


def test_constant_only_selection_and_automatic_type_dependencies(source, tmp_path):
    output = tmp_path / 'constant'
    stream = io.StringIO()
    assert main(['export', '--constant', 'DEFAULT_PACKET', '--sv-source', str(source),
                 '--out', str(output)], out=stream) == 0
    assert 'from svx_mirror.values import DEFAULT_PACKET' in stream.getvalue()
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['constants']] == ['values::DEFAULT_PACKET']
    assert {item['symbol'] for item in data['value_types']} == {'values::State', 'values::Packet'}
    import_generated(output, 'from svx_mirror.values import DEFAULT_PACKET; assert DEFAULT_PACKET.tag.value == 129')


def test_plain_constant_does_not_create_fake_type_export(source, tmp_path):
    output = tmp_path / 'scalar'
    assert main(['export', '--constant', 'COUNT', '--sv-source', str(source),
                 '--out', str(output)], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert 'value_types' not in data
    import_generated(output, 'from svx_mirror.values import COUNT; assert COUNT == 18')


def test_imports_resolve_but_do_not_export_constants_unless_recursive(source):
    kwargs = {'sv_source_files': [source], 'sv_package_targets': ['values']}
    direct = manifest_from_declarations(**kwargs)
    assert 'dependency::DEPTH' not in {item.symbol for item in direct.constants}
    recursive = manifest_from_declarations(**kwargs, sv_recursive_packages=True)
    assert 'dependency::DEPTH' in {item.symbol for item in recursive.constants}


def test_constant_exclusions_and_dependency_type_rejection(source):
    selected = manifest_from_declarations(sv_source_files=[source], sv_package_targets=['values'],
                                          sv_exclude_constants=['DEFAULT_*', 'TABLE'])
    assert all(not item.name.startswith('DEFAULT_') and item.name != 'TABLE' for item in selected.constants)
    with pytest.raises(SVXInheritanceError, match='requires excluded SV value type.*Packet'):
        manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['DEFAULT_PACKET'],
                                   sv_exclude_types=['Packet'])
    with pytest.raises(SVXInheritanceError, match='selection is empty after exclusions'):
        manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['COUNT'],
                                   sv_exclude_constants=['*'])


def test_constant_selector_rejects_runtime_const_and_unknown_targets(source):
    for target in ('RUNTIME_VALUE', 'Missing'):
        with pytest.raises(SVXInheritanceError, match='matched no package parameter/localparam'):
            manifest_from_declarations(sv_source_files=[source], sv_constant_targets=[target])


def test_ambiguous_constant_requires_qualification(tmp_path):
    source = tmp_path / 'ambiguous.sv'
    source.write_text('package a; parameter int N=1; endpackage\n'
                      'package b; parameter int N=2; endpackage', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='ambiguous SV constant.*a::N, b::N'):
        manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['N'])
    selected = manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['b::N'])
    assert selected.constants[0].symbol == 'b::N'


def test_manifest_constant_encoding_and_schema_are_validated(source):
    original = manifest_dict(manifest_from_declarations(sv_source_files=[source], sv_constant_targets=['COUNT']))
    assert manifest_dict(parse_manifest(original)) == original
    for key, value in [('data', 'ff'), ('data', original['constants'][0]['data'] + '00'),
                       ('schema', {'kind': 'invalid'}), ('encoding_descriptor', {})]:
        data = json.loads(json.dumps(original))
        data['constants'][0][key] = value
        with pytest.raises(SVXInheritanceError, match='invalid constant export'):
            parse_manifest(data)


def test_named_constant_roundtrip_uses_public_value_modules(source):
    data = manifest_dict(manifest_from_declarations(sv_source_files=[source],
                                                   sv_constant_targets=['DEFAULT_PACKET']))
    manifest = parse_manifest(data)
    with value_modules(manifest.value_types):
        item = manifest.constants[0].as_dict()
        codec = svtypes.materialize_type_spec(svtypes.type_spec_from_identity(
            item['svtypes'], location=item['symbol']), location=item['symbol'])
        value, count = codec.unpack(bytes.fromhex(item['data']))
        assert count == len(bytes.fromhex(item['data']))
        assert value.tag.value == 129 and str(value.flags.value) == 'xz10'


def test_invalid_compile_time_expression_does_not_publish(tmp_path):
    source = tmp_path / 'invalid.sv'
    source.write_text('package p; parameter int N=DOES_NOT_EXIST; endpackage', encoding='utf-8')
    output = tmp_path / 'generated'
    with pytest.raises(SVXInheritanceError):
        main(['export', '--constant', 'N', '--sv-source', str(source), '--out', str(output)], out=io.StringIO())
    assert not output.exists()


def test_zero_empty_negative_logic_and_wide_values(tmp_path):
    source = tmp_path / 'edge_values.sv'
    source.write_text('''package edges;
  localparam int ZERO=0;
  localparam string EMPTY="";
  localparam logic signed [3:0] NEGATIVE=-1;
  localparam logic [95:0] ALL_X='x;
  localparam logic [95:0] ALL_Z='z;
  localparam bit [95:0] WIDE=96'h12345678_9abcdef0_fedcba98;
endpackage''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'edges', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    import_generated(output, '''from svx_mirror.edges import *
assert ZERO == 0 and EMPTY == '' and str(NEGATIVE) == '1111'
assert str(ALL_X) == 'x'*96 and str(ALL_Z) == 'z'*96
assert WIDE == 0x123456789abcdef0fedcba98
''')


def test_integer_state_domains_follow_native_types(tmp_path):
    source = tmp_path / 'unknown_integer.sv'
    source.write_text("package p; localparam int N='x; localparam integer I='x; endpackage", encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'p', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    import_generated(output, "from svx_mirror.p import N,I; assert N == 0 and str(I) == 'x'*32")


def test_import_rejects_changed_public_encoding(source, tmp_path):
    output = tmp_path / 'generated'
    assert main(['export', '--constant', 'COUNT', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    import_generated(output, '''import svtypes
original=svtypes.encoding_descriptor
class Changed:
    def to_dict(self):
        return {'binary_format_version': 999}
svtypes.encoding_descriptor=lambda value: Changed()
try:
    from svx_mirror.values import COUNT
except RuntimeError as error:
    assert 'regenerate SV exports' in str(error)
else:
    raise AssertionError('stale constant bytes accepted')
''')
