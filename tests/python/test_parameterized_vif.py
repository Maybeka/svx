import io
import json
from pathlib import Path

import pytest

from svx.cli import main
from svx.vif_names import vif_module_parts

pytest.importorskip('pyslang')


def export(source, output, selector='p'):
    args = ['export', '--package', selector, '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main([*args, '--check'], out=io.StringIO()) == 0
    return json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('spelling,width', [('', 8), ('#(8)', 8), ('#(13)', 13), ('#(.W(13))', 13)])
@pytest.mark.parametrize('modport', ['', '.access'])
def test_parameterized_vif_default_and_explicit_types(tmp_path, spelling, width, modport):
    source = tmp_path / 'bus.sv'
    source.write_text(f'''interface bus#(parameter int W=8);
bit[W-1:0] data;
modport access(inout data);
endinterface
package p;
typedef virtual bus{spelling}{modport} Bus;
class Owner; Bus value; function new(Bus value);this.value=value;endfunction endclass
endpackage''', encoding='utf-8')
    manifest = export(source, tmp_path / 'generated')
    handle = manifest['classes'][0]['fields'][0]['handle']
    assert handle['sv_type'] == f'virtual bus#(.W({width})){modport}'
    assert handle['target_type_name'] == f'sv-vif://bus#(.W({width}))/{modport[1:] or "full"}'
    read = next(op for op in handle['operations'] if op['method']['name'] == 'read_data')
    assert read['method']['return_type']['sv'] == f'bit[{width-1}:0]' or (
        read['method']['return_type']['sv'] == f'bit [{width-1}:0]')
    path = Path(*vif_module_parts(handle['target_type_name'])).with_suffix('.py')
    assert (tmp_path / 'generated/python' / path).is_file()


def test_multiple_specializations_type_arguments_and_array_dimensions(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'integration/parameterized_vif.sv'
    output = tmp_path / 'generated'
    manifest = export(source, output, 'parameterized_vif_pkg')
    methods = {method['name']: method for method in manifest['classes'][0]['methods']}
    handles = {name: methods[name]['return_handle'] for name in
               ('get_default', 'get_same', 'get_wide', 'get_typed', 'get_alias')}
    assert handles['get_default'] == handles['get_same']
    assert handles['get_typed'] == handles['get_alias']
    assert len({h['target_type_name'] for h in handles.values()}) == 3
    for name, width, count in [('get_default',8,3), ('get_wide',13,2), ('get_typed',7,2)]:
        ops = {op['method']['name']: op['method'] for op in handles[name]['operations']}
        assert ops['echo']['return_type']['encoding_descriptor']['unified_type_name'].startswith(
            f'svtypes.Bit[width={width},')
        array = ops['read_lanes']['return_type']['svtypes']
        assert array['kind'] == 'collection' and array['name'] == 'Array'
        assert array['args'][1] == count
        assert array['args'][0]['args'][0] == [8 if name == 'get_default' else 13]
        assert ops['exchange']['timing'] == 'task'
    from svx.inheritance import load_manifest, _vif_module_parts, _manifest_handle_bindings
    model = load_manifest(output / 'inheritance.json')
    bindings = [b for b in _manifest_handle_bindings(model) if b.kind == 'virtual_interface']
    assert len({b.target_type_name for b in bindings}) == 5
    for binding in bindings:
        assert (output / 'python' / Path(*_vif_module_parts(binding)).with_suffix('.py')).is_file()


def test_vif_parameter_names_are_losslessly_encoded_without_hashes():
    targets = ['sv-vif://bus#(.LABEL("a/b"))/full', 'sv-vif://bus#(.LABEL("a_b"))/full',
               'sv-vif://bus#(.LABEL("a_x2f_b"))/full']
    parts = [vif_module_parts(target) for target in targets]
    assert len(set(parts)) == 3
    assert all(all(part.isidentifier() for part in path) for path in parts)
    assert vif_module_parts('sv-vif://bus/access') == ('svx_vif', 'bus', 'access')


def test_inbound_parameterized_reference_lazily_loads_its_view(monkeypatch):
    from types import SimpleNamespace
    import svx.inheritance as inheritance
    target = 'sv-vif://bus#(.W(13))/access'
    reference = SimpleNamespace(target_type_name=target, object_number=1)
    class View:
        def __init__(self, value):
            self.reference = value
    registry = {}
    imports = []
    monkeypatch.setattr(inheritance, '_vif_views', registry)
    def load(module):
        imports.append(module)
        registry[target] = View
    monkeypatch.setattr(inheritance.importlib, 'import_module', load)
    view = inheritance._decode_vif_view(reference)
    assert view.reference is reference
    assert imports == ['.'.join(vif_module_parts(target))]


def test_scalar_parameter_values_and_localparams(tmp_path):
    source = tmp_path / 'scalar.sv'
    source.write_text('''interface bus#(parameter string LABEL="a/b c", parameter real SCALE=1.5,
parameter logic[3:0] FLAGS=4'bx01z, parameter int W=8);
localparam int K=W+1;
bit[K-1:0] data;
endinterface
package p;
typedef virtual bus Bus;
class Owner;Bus value;endclass
endpackage''', encoding='utf-8')
    manifest = export(source, tmp_path / 'generated')
    handle = manifest['classes'][0]['fields'][0]['handle']
    assert '.LABEL("a/b c")' in handle['sv_type']
    assert '.SCALE(1.5)' in handle['sv_type']
    assert ".FLAGS(4'bx01z)" in handle['sv_type']
    assert '.K(' not in handle['sv_type']
    assert '%2F' in handle['target_type_name'] and '%20' in handle['target_type_name']
    assert not any(character.isspace() for character in handle['target_type_name'])
    assert handle['operations'][0]['method']['return_type']['sv'].replace(' ', '') == 'bit[8:0]'


@pytest.mark.parametrize('declaration', [
    'typedef enum bit[1:0] {IDLE,ACTIVE} Value;',
    'typedef struct packed {bit[7:0] data;} Value;',
])
def test_package_nominal_type_arguments_are_not_interface_local_types(tmp_path, declaration):
    source = tmp_path / 'nominal.sv'
    source.write_text(f'''package q;{declaration}endpackage
interface bus#(parameter type T=q::Value);
T value;
T values[2];
function T echo(input T data);return data;endfunction
endinterface
package p;typedef virtual bus Bus;class Owner;Bus bus;endclass endpackage''', encoding='utf-8')
    manifest = export(source, tmp_path / 'generated')
    handle = manifest['classes'][0]['fields'][0]['handle']
    assert handle['sv_type'] == 'virtual bus#(.T(q::Value))'
    assert 'q::Value' in {value['symbol'] for value in manifest['value_types']}
    ops = {op['method']['name']: op['method'] for op in handle['operations']}
    assert ops['echo']['return_type']['sv'] == 'q::Value'
    assert ops['read_value']['return_type'] == ops['echo']['return_type']
    assert ops['read_values']['return_type']['svtypes']['name'] == 'Array'


def test_long_parameter_values_do_not_create_oversized_filenames(tmp_path):
    source = tmp_path / 'long.sv'
    source.write_text('interface bus#(parameter string LABEL="' + 'a' * 350 + '");'
                      'bit data;endinterface package p;typedef virtual bus Bus;'
                      'class Owner;Bus bus;endclass endpackage', encoding='utf-8')
    output = tmp_path / 'generated'
    manifest = export(source, output)
    target = manifest['classes'][0]['fields'][0]['handle']['target_type_name']
    parts = vif_module_parts(target)
    assert len(parts) > 4 and max(map(len, parts)) <= 103
    assert (output / 'python' / Path(*parts).with_suffix('.py')).is_file()
