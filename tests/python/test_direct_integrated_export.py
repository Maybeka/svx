import io
import json

import pytest

from svx.cli import main
from test_sv_nested_classes import subprocess_import

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    include = tmp_path / 'classes.svh'
    include.write_text('''class Outer;
typedef enum bit[3:0] {IDLE=0, RUN=3} Mode;
typedef struct packed {Mode mode;logic[3:0] flags;} Packet;
class Inner;
int count;
function new(int seed);count=seed;endfunction
function Packet echo(Packet value);return value;endfunction
endclass
typedef Inner Alias;
endclass''', encoding='utf-8')
    source = tmp_path / 'project.sv'
    source.write_text('''`define ORIGINAL_WIDTH 7
package p;
`include "classes.svh"
typedef bit[`ORIGINAL_WIDTH-1:0] Word;
parameter int COUNT=9;
function Outer::Packet echo(Outer::Packet value);return value;endfunction
endpackage
module original_top;
initial $display("original top");
endmodule''', encoding='utf-8')
    return source


def test_integrated_package_preserves_original_types_and_record_order(source, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--package', 'p', '--integrated', '--sv-source', str(source),
            '-I', str(tmp_path), '--out', str(output)]
    stream = io.StringIO()
    assert main(args, out=stream) == 0
    assert 'compile in place of supplied SV sources' in stream.getvalue()
    text = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert text.count('package svx_call_records_pkg;') == 1
    assert text.index('endpackage') < text.index('package svx_call_records_pkg;')
    assert text.index('package svx_call_records_pkg;') < text.index('module original_top;')
    assert 'typedef p::Outer::Mode' in text
    assert text.count('class Outer;') == 1 and text.count('class Inner;') == 1
    assert 'extends p::Outer::Inner' in text
    assert (tmp_path / 'classes.svh').read_text(encoding='utf-8').startswith('class Outer;')
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in output.rglob('*') if path.is_file()}
    assert main(args + ['--check'], out=io.StringIO()) == 0
    assert main(args, out=io.StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in output.rglob('*') if path.is_file()}
    subprocess_import(output, '''from svx_mirror.p import Outer, Word, COUNT, echo
assert isinstance(Outer,type) and isinstance(Outer.Inner,type)
assert Outer.Packet.__name__ == 'Packet'
assert Word().width == 7 and COUNT == 9
assert callable(echo)
''')


@pytest.mark.parametrize('selector,target', [
    ('--class', 'p::Outer::Inner'), ('--class', 'p::Outer::Alias'),
    ('--type', 'p::Outer::Packet'), ('--constant', 'p::COUNT'), ('--callable', 'p::echo'),
])
def test_integrated_independent_symbol_kinds(source, tmp_path, selector, target):
    output = tmp_path / 'generated'
    args = ['export', selector, target, '--integrated', '--sv-source', str(source),
            '-I', str(tmp_path), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    text = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert text.count('class Outer;') == 1
    if selector == '--class':
        assert 'extends ' + target in text
    if selector == '--callable':
        assert 'p::echo(' in text
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['generation_inputs']['source_mode'] == 'separate-parse-inputs'
    subprocess_import(output, 'import svx_mirror.p')
