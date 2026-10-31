import io
import json

import pytest

from svx.cli import main
from svx.declarations import manifest_from_declarations
from test_sv_nested_classes import subprocess_import

pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'nested.sv'
    path.write_text('''class Outer;
class Inner;
int count;
function new(int seed);count=seed;endfunction
virtual function int status();return count;endfunction
endclass
typedef Inner Alias;
endclass
class OtherOuter;
class Inner extends Outer::Inner;
function new(int seed);super.new(seed+1);endfunction
endclass
endclass
class Outer_Inner;endclass
class outer;
class Inner;endclass
endclass
''', encoding='utf-8')
    return path


def run(source, output, *selectors):
    args = ['export', '--class', *selectors, '--sv-source', str(source), '--out', str(output)]
    message = io.StringIO()
    assert main(args, out=message) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    return message.getvalue()


def test_unit_inner_export_keeps_namespace_and_does_not_export_outer(source, tmp_path):
    output = tmp_path / 'generated'
    message = run(source, output, '$unit::Outer::Inner')
    assert 'from svx_mirror_unit.unit_0 import Outer' in message
    assert 'Type: svx_mirror_unit.unit_0.Outer.Inner' in message
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['classes']] == ['$unit::Outer::Inner']
    artifacts = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['generated_types'][0]['python_fqn'] == 'svx_mirror_unit.unit_0.Outer.Inner'
    subprocess_import(output, '''from types import SimpleNamespace
from svx_mirror_unit.unit_0 import Outer
assert isinstance(Outer,SimpleNamespace)
assert Outer.Inner.__name__=='Inner'
assert Outer.Inner.__module__=='svx_mirror_unit.unit_0'
assert Outer.Inner.__qualname__=='Outer.Inner'
assert Outer.Inner.__svx_foreign_class_id__=='sv://unit/0/Outer/Inner'
''')


def test_all_unit_classes_attach_nested_types_to_real_outer_and_keep_aliases(source, tmp_path):
    output = tmp_path / 'all'
    run(source, output, '$unit::*')
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Outer,OtherOuter,Outer_Inner,outer
assert isinstance(Outer,type) and isinstance(OtherOuter,type)
assert Outer.Inner is not OtherOuter.Inner and Outer.Inner is not outer.Inner
assert Outer.Inner.__name__==OtherOuter.Inner.__name__==outer.Inner.__name__=='Inner'
assert Outer.Alias.__name__=='Alias'
assert Outer.Alias.__qualname__=='Outer.Alias'
assert Outer_Inner.__name__=='Outer_Inner'
''')
    text = (output / 'sv/source.sv').read_text(encoding='utf-8')
    assert 'extends $unit::Outer::Inner' in text and 'extends $unit::OtherOuter::Inner' in text
    helpers = [line.strip().split()[1] for line in text.splitlines()
               if line.strip().startswith('class svx_unit_mirror_')]
    assert len(helpers) == len(set(helpers))
    files = [str(path.relative_to(output)).casefold() for path in output.rglob('*.py')]
    assert len(files) == len(set(files))


def test_unit_nested_lineage_preserves_declaring_class_path(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['OtherOuter::Inner'])
    parent, = manifest.classes[0].base_lineage
    assert parent.symbol == '$unit::Outer::Inner'
    assert parent.canonical_id == 'sv://unit/0/Outer/Inner'


def test_same_nested_class_names_from_independent_units_keep_public_owners(tmp_path):
    sources = [tmp_path / 'one.sv', tmp_path / 'two.sv']
    for path in sources:
        path.write_text('class Outer;class Inner;endclass endclass', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', '$unit::*::Inner', '--sv-source', str(sources[0]),
            '--sv-source', str(sources[1]), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    subprocess_import(output, '''from svx_mirror_unit.unit_0 import Outer as First
from svx_mirror_unit.unit_1 import Outer as Second
assert First.Inner is not Second.Inner
assert First.Inner.__qualname__==Second.Inner.__qualname__=='Outer.Inner'
''')
