import io
import json

import pytest

from svx.cli import main


pytest.importorskip('pyslang')


@pytest.mark.parametrize('declaration', [
    'typedef int value_t;',
    'typedef byte value_t;',
    'typedef shortint value_t;',
    'typedef longint value_t;',
    'typedef time value_t;',
    'typedef bit [7:0] value_t;',
    'typedef bit [1:0][7:0] value_t;',
    'typedef logic signed [15:0] value_t;',
    'typedef string value_t;',
    'typedef real value_t;',
    'typedef shortreal value_t;',
    'typedef enum bit [1:0] { ZERO, ONE } value_t;',
    'typedef struct packed { bit [7:0] data; } value_t;',
    'typedef struct { int data; } value_t;',
    'class Value; int data; endclass typedef Value value_t;',
])
def test_source_typedef_collections(tmp_path, declaration):
    source = tmp_path / 'types.sv'
    source.write_text(f'''
package types_pkg;
  {declaration}
endpackage
package target_pkg;
  typedef types_pkg::value_t value_alias_t;
  typedef value_alias_t value_alias2_t;
  typedef value_alias2_t queue_t[$];
  typedef queue_t queue_alias_t;
  typedef queue_alias_t nested_queue_t[$];
  class Driver;
    queue_alias_t q;
    nested_queue_t nested;
    value_alias2_t d[];
    value_alias2_t a[3];
    value_alias2_t m[int];
  endclass
endpackage
''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'target_pkg', '--sv-source', str(source),
                 '--out', str(output)], out=io.StringIO()) == 0
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    driver = next(item for item in manifest['classes'] if item['symbol'] == 'target_pkg::Driver')
    assert {field['name'] for field in driver['fields']} == {'q', 'nested', 'd', 'a', 'm'}


def test_virtual_interface_typedef_collection(tmp_path):
    source = tmp_path / 'vif.sv'
    source.write_text('''
interface bus_if; logic [7:0] data; endinterface
package types_pkg; typedef virtual bus_if vif_t; endpackage
package target_pkg;
  typedef types_pkg::vif_t alias_t;
  class Driver; alias_t vifs[$]; endclass
endpackage
''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'target_pkg', '--sv-source', str(source),
                 '--out', str(output)], out=io.StringIO()) == 0
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    driver = next(item for item in manifest['classes'] if item['symbol'] == 'target_pkg::Driver')
    field = next(item for item in driver['fields'] if item['name'] == 'vifs')
    assert field['handle']['kind'] == 'virtual_interface'


def test_cross_package_enum_associative_key(tmp_path):
    source = tmp_path / 'enum_key.sv'
    source.write_text('''
package types_pkg;
  typedef enum bit [1:0] { ZERO, ONE } key_t;
endpackage
package target_pkg;
  typedef types_pkg::key_t key_alias_t;
  class Driver; int values[key_alias_t]; endclass
endpackage
''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'target_pkg', '--sv-source', str(source),
                 '--out', str(output)], out=io.StringIO()) == 0
