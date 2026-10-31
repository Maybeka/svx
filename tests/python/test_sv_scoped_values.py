import io
import json

import pytest

from svx.cli import main
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import load_manifest
from test_sv_nested_classes import subprocess_import

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'scoped_values.sv'
    path.write_text('''package p;
class Outer;
  typedef enum bit [3:0] {IDLE=0, RUN=3} Mode;
  typedef struct packed {Mode mode; logic [3:0] flags;} Packet;
  typedef Packet Alias;
  local typedef bit [3:0] Hidden;
  protected typedef bit [4:0] Protected;
  class Inner;
    typedef bit [7:0] Word;
    function Packet echo(Packet value);return value;endfunction
  endclass
endclass
class Other;
  typedef enum bit [3:0] {IDLE=1, RUN=5} Mode;
endclass
endpackage''', encoding='utf-8')
    return path


def test_scoped_type_only_preserves_identity_and_does_not_export_owner(source, tmp_path):
    output = tmp_path / 'types'
    args = ['export', '--type', 'p::Outer::Packet', 'p::Outer::Alias',
            'p::Outer::Inner::Word', 'p::Other::Mode', '--sv-source', str(source), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    raw = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert raw['classes'] == []
    assert manifest_dict(load_manifest(output / 'inheritance.json'))['value_types'] == raw['value_types']
    subprocess_import(output, '''from svx_mirror.p import Outer, Other
from types import SimpleNamespace
import sys, svtypes
assert isinstance(Outer, SimpleNamespace)
assert Outer.Mode.RUN == 3 and Other.Mode.RUN == 5
assert Outer.Packet.__name__ == 'Packet'
assert Outer.Packet.__qualname__ == 'Outer.Packet'
assert Outer.Packet.__module__ == 'svx_mirror.p'
assert Outer.Alias is Outer.Packet
assert Outer.Inner.Word().width == 8
p=Outer.Packet();p.mode.value=Outer.Mode.RUN;p.flags.value='10xz'
q=Outer.Packet();q.from_bytes(p.to_bytes())
assert q.mode.value == Outer.Mode.RUN
assert q.flags.value == svtypes.LogicValue.from_string('10xz')
identity=svtypes.type_spec_identity(Outer.Packet)
assert svtypes.type_spec_from_identity(identity) is Outer.Packet
assert 'svx' not in sys.modules
''')


def test_package_class_and_value_namespaces_coexist(source, tmp_path):
    output = tmp_path / 'package'
    assert main(['export', '--package', 'p', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    subprocess_import(output, '''from svx_mirror.p import Outer, Other
assert isinstance(Outer, type) and isinstance(Outer.Inner, type)
assert isinstance(Other, type)
assert Outer.Packet.__qualname__ == 'Outer.Packet'
assert Outer.Inner.Word().width == 8
assert not hasattr(Outer,'Hidden') and not hasattr(Outer,'Protected')
''')


def test_class_signature_discovers_scoped_dependencies(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['p::Outer::Inner'])
    assert {item.symbol for item in manifest.value_types} == {'p::Outer::Mode', 'p::Outer::Packet'}


def test_nested_class_only_registers_contract_with_unselected_owner(source, tmp_path):
    output = tmp_path / 'inner'
    assert main(['export', '--class', 'p::Outer::Inner', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    subprocess_import(output, '''from svx_mirror.p import Outer
from types import SimpleNamespace
assert isinstance(Outer,SimpleNamespace)
assert isinstance(Outer.Inner,type)
assert Outer.Packet.__qualname__ == 'Outer.Packet'
assert Outer.Mode.RUN == 3
''')


@pytest.mark.parametrize('owner', ['_svx_types', '_svx_sys', '_svx_values', '_svx_value_namespace'])
def test_nested_owner_names_do_not_overwrite_generated_support(tmp_path, owner):
    source = tmp_path / 'names.sv'
    source.write_text(f'''package p;class {owner};
typedef enum bit[3:0] {{READY=3}} Mode;
typedef struct packed {{Mode mode;logic[3:0] data;}} Packet;
endclass endpackage''', encoding='utf-8')
    output = tmp_path / 'generated'
    assert main(['export', '--type', f'p::{owner}::Packet', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    subprocess_import(output, f'''from svx_mirror.p import {owner}
p={owner}.Packet();p.mode.value={owner}.Mode.READY
assert p.mode.value == 3
''')


def test_inaccessible_named_type_dependency_fails_before_publication(tmp_path):
    source = tmp_path / 'hidden.sv'
    source.write_text('''package p;class O;
local typedef enum bit[3:0] {READY=3} Hidden;
function Hidden status();return READY;endfunction
endclass endpackage''', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='is local.*accessible public type'):
        manifest_from_declarations(sv_source_files=[source], sv_class_targets=['p::O'])
