from io import StringIO
import json

from svx.cli import main
from svx.declarations import manifest_dict
from svx.inheritance import parse_manifest, load_manifest


def test_export_keeps_constructor_defaults_and_separates_dispatch_and_factories(tmp_path):
    output = tmp_path / 'generated'
    arguments = ['export', '--package', 'constructor_defaults_pkg', '--sv-source',
                 'tests/integration/constructor_defaults.sv', '--out', str(output)]
    assert main(arguments, out=StringIO()) == 0
    raw = json.loads((output / 'inheritance.json').read_text())
    model = load_manifest(output / 'inheritance.json')
    assert model.schema_version == '2.9.0'
    parameters = model.classes[0].constructor.parameters
    assert [p.sv_default for p in parameters] == ['7', '"default-driver"']
    serialized = manifest_dict(model)
    serialized.pop('discovery_provenance', None)
    assert parse_manifest(serialized).classes == model.classes
    core = (output / 'mirrors.sv').read_text()
    assert 'input int seed = 7, input string label = "default-driver"' in core
    assert 'super.new(seed, label);' in core
    assert '`SVX_BIND_CONSTRUCTED_OBJECT(' in core
    constructor = core.split('function new(input int seed', 1)[1].split('endfunction', 1)[0]
    assert '::encode_arguments(seed, label)' in constructor
    assert 'if (' not in constructor and 'chandle' not in constructor and ' = new(' not in constructor
    records = (output / 'support/mirrors_call_records.svh').read_text()
    assert 'static function chandle encode_arguments(input int seed, input string label)' in records
    assert '_svx__record.seed = seed;' in records
    assert '_svx__record.label = label;' in records
    task = core.split('virtual task _svx__sv_invoke(', 1)[1].split('endtask', 1)[0]
    function = core.split('virtual function void _svx__sv_invoke_function(', 1)[1].split('endfunction', 1)[0]
    assert '#advance' in task and '#get_seed' not in task and '@svx_field' not in task
    assert '#get_seed' in function and '#advance' not in function and '@svx_field' in function
    factories = (output / 'support/mirrors_factories.svh').read_text()
    assert 'implements svx_factory' not in core
    assert 'implements svx_factory' in factories
    assert 'svx_constructor_ids::prepare(' in factories
    assert 'svx_instance = new(seed, label);' in factories
    assert '`include "support/mirrors_factories.svh"' in core
    assert main([*arguments, '--check'], out=StringIO()) == 0


def test_sv_construction_can_bind_plain_loaded_mirror_without_override(monkeypatch):
    import svx.inheritance as inheritance
    import svx.declarations as declarations

    constructed = []
    class Mirror:
        @classmethod
        def __svx_create_from_sv__(cls, object_id, *args):
            constructed.append((object_id, args))

    class_id = 'sv://plain/Driver'
    monkeypatch.setattr(inheritance, '_constructor_contracts', {})
    monkeypatch.setattr(inheritance, '_python_subclasses', {})
    monkeypatch.setattr(declarations, '_source_mirror_implementations', {class_id: Mirror})
    inheritance.register_constructor(class_id, ())
    inheritance._create_python_instance(class_id, 17, b'')
    assert constructed == [(17, ())]


def test_constructor_encoder_avoids_original_argument_names(tmp_path):
    source = tmp_path / 'names.sv'
    source.write_text('''package names;
      class Driver;
        function new(int encode = 4, int encode_arguments = 5); endfunction
      endclass
    endpackage''')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'names', '--sv-source', str(source),
                 '--out', str(output)], out=StringIO()) == 0
    core = (output / 'mirrors.sv').read_text()
    records = (output / 'support/mirrors_call_records.svh').read_text()
    assert '::_svx__encode_arguments(encode, encode_arguments)' in core
    assert 'static function chandle _svx__encode_arguments(input int encode, input int encode_arguments)' in records
    assert 'return _svx__record._svx__encode();' in records
