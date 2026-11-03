import io

import pytest

from svx.cli import main


@pytest.mark.parametrize('modport', [False, True])
def test_vif_array_signal_uses_unpacked_type_for_dispatch(tmp_path, modport):
    pytest.importorskip('pyslang')
    source = tmp_path/'array_bus.sv'
    text = '''interface array_bus;
  bit [7:0] values[4];
  bit [2:0][7:0] vectors[2][3];
  modport access(inout values, vectors);
endinterface
package array_owner_pkg;
  typedef virtual array_bus.access Bus;
  class Owner;
    Bus bus;
    function new(Bus bus); this.bus=bus; endfunction
  endclass
endpackage
'''
    if not modport:
        text = text.replace('virtual array_bus.access', 'virtual array_bus')
    source.write_text(text, encoding='utf-8')
    output = tmp_path/'generated'
    assert main(['export', '--package', 'array_owner_pkg', '--sv-source', str(source),
                 '--out', str(output)], out=io.StringIO()) == 0
    sv = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*')
                   if path.suffix in {'.sv', '.svh'})
    for malformed in ('bit [7:0] [4] result;', 'bit [7:0] [4] value_to_write;',
                      'bit [2:0] [7:0] [3] [2] result;',
                      'bit [2:0] [7:0] [3] [2] value_to_write;'):
        assert malformed not in sv
    assert 'value.values' in sv and 'value.vectors' in sv
