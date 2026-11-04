import pytest

from svx.struct_contract import bind_native_struct_declaration


@pytest.mark.parametrize('width', [9, 70])
def test_native_struct_helpers_use_validated_width_not_parameter_value_scope(width):
    source = f'typedef struct packed {{ logic [{width}-1:0] data; }} Packet_t;\n' + '''class Packet_packer;
  static function void update(ref Packet_t value);
    logic [$bits(value.data)-1:0] member;
    operations#(logic [$bits(value.data)-1:0])::apply(member);
  endfunction
endclass
'''
    text = bind_native_struct_declaration(source, 'Packet', 'pkg::View::Packet', packed=True,
        schema={'fields': [{'name': 'data', 'type': {'kind': 'logic', 'width': width}}]})
    assert text.startswith('typedef pkg::View::Packet Packet_t;')
    assert '$bits(value.data)' not in text
    assert text.count(f'logic [{width}-1:0]') == 2
