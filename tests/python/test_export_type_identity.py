from io import StringIO
from pathlib import Path

from svx.cli import main
from svx.inheritance import _sv_specialization_value


def test_specialization_literals_preserve_width_and_signedness():
    assert _sv_specialization_value(65535, 'logic[31:0]') == "32'd65535"
    assert _sv_specialization_value(-1, 'logic signed[7:0]') == "-8'sd1"
    assert _sv_specialization_value(65535, 'int unsigned') == "32'd65535"
    assert _sv_specialization_value(3, 'int') == '3'
    assert _sv_specialization_value((1 << 63) + 1, 'logic[63:0]') == "64'd9223372036854775809"


def test_export_helpers_do_not_collide_with_suffix_fields(tmp_path):
    source = Path('tests/integration/type_identity.sv')
    output = tmp_path / 'generated'
    arguments = ['export', '--class', 'type_identity_pkg::Driver', '--sv-source', str(source),
                 '--out', str(output)]
    assert main(arguments, out=StringIO()) == 0
    core = (output / 'mirrors.sv').read_text()
    fields = (output / 'support/mirrors_fields.svh').read_text()
    records = (output / 'support/mirrors_call_records.svh').read_text()
    assert "#(32'd65535, -8'sd1, 64'd9223372036854775809)" in core
    assert '_svx__type_``NAME' in fields and '_svx__field_``NAME' in fields
    assert 'NAME``_type' not in fields and 'NAME``_read' not in fields
    assert '`SVX_FIELD_READ_PAYLOAD(' in fields and '`SVX_FIELD_WRITE_PAYLOAD(' in fields
    for name in ('data', 'data_type', 'data_read', 'data_write'):
        assert f'      {name},' in core
    assert 'covergroup' not in records and 'coverpoint' not in records
    assert 'rand int' not in records
    assert 'pack_body(' in records and 'unpack_body(' in records
    assert 'function chandle encode()' in records
    assert 'static function' in records and ' decode(input chandle payload)' in records
    assert main([*arguments, '--check'], out=StringIO()) == 0
