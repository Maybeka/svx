import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import pytest

from svx.cli import main
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import artifact_manifest, emit_python_mirrors, emit_sv_mirrors, parse_manifest
from svx.sv_scan import scan_sv_sources

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'nested.sv'
    path.write_text('''package base_pkg;
class Base;
  int count;
  function new(int seed); count=seed; endfunction
  virtual function int status(); return count; endfunction
endclass endpackage
package classes_pkg;
import base_pkg::*;
class Outer;
  class Inner extends Base;
    function new(int seed); super.new(seed+1); endfunction
    function int status(); return super.status()+10; endfunction
    static function int twice(int value);return value*2;endfunction
  endclass
  typedef Inner Alias;
endclass
class OtherOuter;
  class Inner extends Outer::Inner;
    function new(int seed);super.new(seed+1);endfunction
  endclass
endclass
class Outer_Inner extends Base;
  function new(int seed);super.new(seed);endfunction
endclass
endpackage
module not_a_package;
  class NotYetExported;endclass
endmodule''', encoding='utf-8')
    return path


def subprocess_import(output, code):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(output / 'python'), str(root / 'python'), str(root.parent / 'svtypes/python')]))
    result = subprocess.run([sys.executable, '-B', '-c', code], env=env, text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_nested_inventory_and_semantic_base_resolution(source):
    facts = scan_sv_sources([source])
    assert {'classes_pkg::Outer::Inner', 'classes_pkg::Outer::Alias',
            'classes_pkg::OtherOuter::Inner'} <= set(facts)
    assert 'not_a_package::NotYetExported' not in facts
    assert facts['classes_pkg::Outer::Inner'].direct_base == 'base_pkg::Base'
    assert facts['classes_pkg::OtherOuter::Inner'].direct_base == 'classes_pkg::Outer::Inner'
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['classes_pkg::OtherOuter::Inner'])
    assert [item.symbol for item in manifest.classes] == ['classes_pkg::OtherOuter::Inner']
    assert [item.symbol for item in manifest.classes[0].base_lineage] == ['base_pkg::Base', 'classes_pkg::Outer::Inner']
    assert manifest_dict(parse_manifest(manifest_dict(manifest))) == manifest_dict(manifest)


def test_single_nested_target_does_not_construct_or_export_owner(source, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--class', 'classes_pkg::Outer::Inner', '--sv-source', str(source), '--out', str(output)]
    stream = io.StringIO()
    assert main(args, out=stream) == 0
    assert 'Type: svx_mirror.classes_pkg.Outer.Inner' in stream.getvalue()
    assert main(args + ['--check'], out=io.StringIO()) == 0
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['classes']] == ['classes_pkg::Outer::Inner']
    subprocess_import(output, '''from types import SimpleNamespace
from svx_mirror.classes_pkg import Outer
assert isinstance(Outer, SimpleNamespace)
assert Outer.Inner.__name__ == 'Inner'
assert Outer.Inner.__module__ == 'svx_mirror.classes_pkg'
assert Outer.Inner.__qualname__ == 'Outer.Inner'
assert Outer.Inner.__svx_foreign_class_id__ == 'sv://classes_pkg/Outer/Inner'
''')


def test_package_nested_types_share_original_owner_class_namespace(source, tmp_path):
    output = tmp_path / 'package'
    assert main(['export', '--package', 'classes_pkg', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    subprocess_import(output, '''from svx_mirror.classes_pkg import Outer, OtherOuter, Outer_Inner
assert isinstance(Outer, type) and isinstance(OtherOuter, type)
assert Outer.Inner.__name__ == OtherOuter.Inner.__name__ == 'Inner'
assert Outer.Inner is not OtherOuter.Inner
assert issubclass(OtherOuter.Inner, Outer.Inner)
assert Outer.Alias.__name__ == 'Alias'
assert Outer.Inner.__qualname__ == 'Outer.Inner'
assert OtherOuter.Inner.__qualname__ == 'OtherOuter.Inner'
assert Outer_Inner.__name__ == 'Outer_Inner'
''')


def test_nested_and_underscore_class_helpers_do_not_collide(source):
    manifest = manifest_from_declarations(sv_source_files=[source],
        sv_class_targets=['classes_pkg::Outer::Inner', 'classes_pkg::Outer_Inner'])
    python = emit_python_mirrors(manifest)
    sv = emit_sv_mirrors(manifest)
    assert 'extends classes_pkg::Outer::Inner' in sv
    assert 'svx_scoped_mirror_' in sv and 'svx_mirror_sv_classes_pkg_Outer_Inner' in sv
    artifacts = artifact_manifest(manifest, python, sv)
    names = {item['canonical_class_id']: item['python_fqn'] for item in artifacts['generated_types']}
    assert names['sv://classes_pkg/Outer/Inner'] == 'svx_mirror.classes_pkg.Outer.Inner'
    assert names['sv://classes_pkg/Outer_Inner'] == 'svx_mirror.classes_pkg.Outer_Inner'


def test_nested_short_names_reject_ambiguity(source):
    with pytest.raises(SVXInheritanceError, match='ambiguous SV class') as error:
        manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Inner'])
    assert 'classes_pkg::Outer::Inner' in str(error.value)
    assert 'classes_pkg::OtherOuter::Inner' in str(error.value)


def test_three_levels_publish_without_extra_owner_mirrors(tmp_path):
    source = tmp_path / 'three.sv'
    source.write_text('''package p;class Outer;class Middle;class Inner;
function int status();return 1;endfunction
endclass endclass endclass endpackage''', encoding='utf-8')
    output = tmp_path / 'three'
    assert main(['export', '--class', 'p::Outer::Middle::Inner', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    subprocess_import(output, '''from types import SimpleNamespace
from svx_mirror.p import Outer
assert isinstance(Outer.Middle, SimpleNamespace)
assert Outer.Middle.Inner.__qualname__ == 'Outer.Middle.Inner'
assert Outer.Middle.Inner.__module__ == 'svx_mirror.p'
''')


def test_nested_private_typedef_is_not_a_public_export(tmp_path):
    source = tmp_path / 'private.sv'
    source.write_text('''package p;class O;class I;endclass
local typedef I Hidden; protected typedef I Protected;
endclass endpackage''', encoding='utf-8')
    facts = scan_sv_sources([source])
    assert 'p::O::I' in facts and 'p::O::Hidden' not in facts and 'p::O::Protected' not in facts


def test_private_scope_paths_and_sv_guards_survive_case_insensitive_hosts(tmp_path):
    source = tmp_path / 'case.sv'
    source.write_text('''package p;
class Outer; class Inner;function int value();return 1;endfunction endclass endclass
class outer; class Inner;function int value();return 2;endfunction endclass endclass
endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['p::*::Inner'])
    generated = emit_python_mirrors(manifest)
    paths = [str(path).casefold() for path in generated]
    assert len(paths) == len(set(paths))
    guards = [line.removeprefix('`ifndef ') for line in emit_sv_mirrors(manifest).splitlines()
              if line.startswith('`ifndef ')]
    assert len(guards) == len(set(guards))
    output = tmp_path / 'generated'
    assert main(['export', '--class', 'p::*::Inner', '--sv-source', str(source), '--out', str(output)],
                out=io.StringIO()) == 0
    subprocess_import(output, '''from svx_mirror.p import Outer, outer
assert Outer.Inner is not outer.Inner
assert Outer.Inner.__qualname__ == 'Outer.Inner'
assert outer.Inner.__qualname__ == 'outer.Inner'
''')
