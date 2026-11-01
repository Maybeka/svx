import io
import json
from pathlib import Path

import pytest

from svx.cli import main

pytest.importorskip('pyslang')


def test_generate_enums_use_local_typed_packers_without_moving_native_types(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'integration/generate_enum_classes.sv'
    source = tmp_path / 'original.sv'
    source.write_text(fixture.read_text(encoding='utf-8') + '''
module tb;
  enum_owner #(9) a();
  enum_owner #(70) b();
endmodule
''', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'tb.*.lane[0].Driver', '--sv-source', str(source), '--out', str(output)]
    main(args, out=io.StringIO())
    before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
              for path in output.rglob('*') if path.is_file()}
    main([*args, '--check'], out=io.StringIO())
    assert {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.rglob('*') if path.is_file()} == before
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(data['classes']) == 2
    assert {item['schema']['width'] for item in data['value_types']} == {9, 70}
    assert all(item['schema']['signed'] for item in data['value_types'])
    generated = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert generated.count('typedef enum bit signed [W-1:0] {IDLE=0, ACTIVE=-1} State;') == 1
    assert 'class SVXLocalEnumPacker_' in generated
    assert 'svtypes_pkg::bit_packer#(SVXInstanceValue_' not in generated
    assert 'svtypes_pkg::bit_packer#(bit [8:0])::unpack(bits, bytes, offset);' in generated
    assert 'svtypes_pkg::bit_packer#(bit [69:0])::unpack(bits, bytes, offset);' in generated


def test_generate_runtime_example_imports_original_filelist_and_all_value_dependencies(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / 'generated'
    args = ['export', '--class', 'tb_generate_runtime_values.*.lane[0].Driver',
            '-f', str(root / 'examples/sv_scoped/generate_runtime_values.f'),
            '--sv-build-directory', str(root), '--out', str(output)]
    main(args, out=io.StringIO())
    before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
              for path in output.rglob('*') if path.is_file()}
    main([*args, '--check'], out=io.StringIO())
    assert {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.rglob('*') if path.is_file()} == before
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(manifest['classes']) == 2
    for source in manifest['classes']:
        assert source['symbol'] == 'Driver'
        assert {field['name'] for field in source['fields']} == {
            'mode', 'payload', 'modes', 'packets', 'samples', 'by_name', 'groups'}
    symbols = {value['symbol'] for value in manifest['value_types']}
    assert symbols >= {
        'Driver::Mode', 'Driver::Payload', 'Driver::Modes', 'Driver::Packets',
        'Driver::Samples', 'Driver::PacketMap', 'Driver::Groups'}
    assert 'Driver::History' not in symbols
    generated = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert 'svtypes_pkg::bit_packer#(SVXInstanceValue_' not in generated
    assert 'SVXLocalEnumPacker_' in generated
