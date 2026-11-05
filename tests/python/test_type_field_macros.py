from io import StringIO
import re

from svx.cli import main


def test_export_shares_concrete_type_macros_and_keeps_native_lvalues(tmp_path):
    source = tmp_path / 'fields.sv'
    source.write_text('''package fields;
      typedef enum bit {IDLE, RUN} state_t;
      typedef enum bit {LOW, HIGH} other_t;
      class Driver;
        state_t first[3], second[3];
        other_t other[3];
        function void exchange(input int index, inout state_t current[3],
                               output state_t previous[3]);
          previous = first; first = current; current[index] = RUN;
        endfunction
      endclass
    endpackage
    ''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'fields', '--sv-source', str(source),
                 '--out', str(output)], out=StringIO()) == 0
    core = (output / 'mirrors.sv').read_text(encoding='utf-8')
    support = (output / 'support/mirrors_fields.svh').read_text(encoding='utf-8')
    definitions = re.findall(r'^`define (\w+)\(NAME, MEMBER, FIELD_ID\)', support, re.M)
    assert len(definitions) == 2
    state = next(name for name in definitions if 'state_t' in name)
    compact = re.sub(r'\s+', '', core)
    assert f'`{state}(_svx__field_first,this.first,' in compact
    assert f'`{state}(_svx__field_second,this.second,' in compact
    assert all(f'`undef {name}' in core for name in definitions)
    assert 'MEMBER[operation.path_index' in support
    assert 'TYPE_OR_ACCESSOR' not in support
    assert 'typedef fields::state_t NAME``_type [3];' in support
    operation = core.split('function void _svx__core_Driver_exchange(', 1)[1].split('endfunction', 1)[0]
    assert '::from_request(req)' in operation
    assert 'super.exchange(req.index, rsp.current, rsp.previous);' in operation
    assert 'rsp.encode()' in operation
    assert 'offset' not in operation and 'bytes' not in operation
    records = (output / 'support/mirrors_call_records.svh').read_text(encoding='utf-8')
    assert 'value.current = request.current;' in records
    assert 'value.previous = request.previous;' not in records
    assert 'static function' in records and ' decode(input chandle payload)' in records


def test_field_macro_expansion_can_be_parsed_with_explicit_types(tmp_path):
    from pyslang import SourceManager
    from pyslang.syntax import SyntaxTree
    from svx.cli import sv_dir
    from svx.sv_scan import _check_source_diagnostics

    source = tmp_path / 'fields.sv'
    source.write_text('package fields; class Driver; int first[3], second[3]; endclass endpackage', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'fields', '--sv-source', str(source),
                 '--out', str(output)], out=StringIO()) == 0
    manager = SourceManager()
    manager.addUserDirectories(str(output))
    manager.addUserDirectories(str(sv_dir().parent))
    tree = SyntaxTree.fromFile(str(output / 'mirrors.sv'), manager)
    _check_source_diagnostics(tree, 'type field macro expansion')


def test_record_api_avoids_original_parameter_names(tmp_path):
    source = tmp_path / 'names.sv'
    source.write_text('''package names; class Driver;
      function void run(input int decode, output int encode, output int from_request);
        encode = decode; from_request = decode + 1;
      endfunction
    endclass endpackage''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'names', '--sv-source', str(source),
                 '--out', str(output)], out=StringIO()) == 0
    core = (output / 'mirrors.sv').read_text(encoding='utf-8')
    records = (output / 'support/mirrors_call_records.svh').read_text(encoding='utf-8')
    assert '::_svx__decode(request);' in core
    assert '::_svx__from_request(req);' in core
    assert 'rsp._svx__encode();' in core
    assert 'super.run(req.decode, rsp.encode, rsp.from_request);' in core
    assert 'function chandle _svx__encode();' in records
