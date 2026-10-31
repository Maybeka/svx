import io
import json

import pytest

from svx.cli import main

pytest.importorskip('pyslang')


def test_program_cli_uses_local_classes_and_zero_time_registration_wait(tmp_path):
    source=tmp_path/'design.sv'
    source.write_text('''program owner#(parameter int WIDTH=8);
class Driver;
bit[WIDTH-1:0] mask;
function new(int seed);mask=seed;endfunction
virtual function int status();return mask;endfunction
static function int width();return WIDTH;endfunction
endclass
endprogram
module tb;owner#(8) a(),b();owner#(13) c();endmodule
''', encoding='utf-8')
    output=tmp_path/'generated'
    args=['export','--class','tb.*.Driver','--sv-source',str(source),'--out',str(output)]
    assert main(args,out=io.StringIO())==0
    assert main(args+['--check'],out=io.StringIO())==0
    artifact=json.loads((output/'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['systemverilog_startup_module']=={'module':'svx_exports','method':'initialize','timing':'task'}
    assert all(item['bridge_kind']=='program' and 'initialize' not in item for item in artifact['instance_bindings'])
    copied=(output/artifact['systemverilog_compile_order'][0]).read_text(encoding='utf-8')
    startup=(output/'sv/exports.sv').read_text(encoding='utf-8')
    assert 'class SVXOwnerInitializer implements svx_owner_initializer' in copied
    assert 'scope == "tb.a"' in copied and 'scope == "tb.b"' in copied
    assert 'SVXInstanceMirror_factory_instance = new()' not in copied
    assert 'extends Driver implements' in copied and 'bind tb.' not in copied
    assert 'task automatic initialize();' in startup
    assert 'wait_initialize_owner(' in startup and '$root.tb.' not in startup
    assert '#0' not in startup and '#1' not in startup


def test_program_generate_scope_reuses_same_initializer_contract(tmp_path):
    source=tmp_path/'design.sv'
    source.write_text('''program owner;
for(genvar I=0;I<2;I++)begin:lane
class Driver;int value;function new(int seed);value=seed+I;endfunction endclass
end
endprogram module tb;owner a();endmodule
''', encoding='utf-8')
    output=tmp_path/'generated'
    assert main(['export','--class','tb.a.lane[*].Driver','--sv-source',str(source),'--out',str(output)],out=io.StringIO())==0
    artifact=json.loads((output/'artifacts.json').read_text(encoding='utf-8'))
    assert all(item['bridge_kind']=='generate' and item['initialization_key'] for item in artifact['instance_bindings'])
    assert artifact['systemverilog_startup_module']['timing']=='task'
