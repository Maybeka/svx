import io

import pytest

from svx.cli import main

pytest.importorskip('pyslang')


@pytest.mark.parametrize('modport', [False, True])
def test_interface_array_signals_preserve_unpacked_dimensions(tmp_path, modport):
    source = tmp_path / 'array_bus.sv'
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
    output = tmp_path / 'generated'
    arguments = ['export', '--package', 'array_owner_pkg', '--sv-source', str(source),
                 '--out', str(output)]
    assert main(arguments, out=io.StringIO()) == 0
    core = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*.sv'))
    texts = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*') if path.suffix in {'.sv', '.svh'})
    assert 'bit [7:0] [4] result;' not in texts
    assert 'bit [7:0] [4] value_to_write;' not in texts
    assert 'bit [2:0] [7:0] [3] [2] result;' not in texts
    assert 'bit [2:0] [7:0] [3] [2] value_to_write;' not in texts
    assert 'return this.value.values;' in core
    assert 'this.value.values = value;' in texts
    assert 'return this.value.vectors;' in texts
    assert 'this.value.vectors = value;' in texts
    assert 'result = svx_core_read_values();' in texts
    assert 'result = svx_core_read_values();' not in core
    assert 'svx_core_write_values(value_to_write);' in texts
