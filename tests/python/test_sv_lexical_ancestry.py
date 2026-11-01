import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from svx.cli import main
from svx.errors import SVXInheritanceError
from svx.source_scopes import instance_public_module

pytest.importorskip('pyslang')


def source_text(container):
    fixture = Path(__file__).resolve().parents[1] / 'integration/lexical_ancestry.sv'
    text = fixture.read_text(encoding='utf-8')
    if container == 'generate':
        text = text.replace('  class Driver extends SharedBase;',
                            '  for(genvar i=0;i<1;i++) begin: lane\n  class Driver extends SharedBase;')
        text = text.replace('  endclass\nendmodule', '  endclass\n  end\nendmodule')
    else:
        text = text.replace('module lexical_owner', container + ' lexical_owner').replace('endmodule', 'end' + container)
    return text + '\nmodule tb; lexical_owner a(),b(); lexical_owner#(13)c(); endmodule\n'


@pytest.mark.parametrize('container', ['module', 'interface', 'program', 'generate'])
@pytest.mark.parametrize('select_base', [False, True])
def test_lexically_visible_unit_ancestor_exports_without_flattening_selected_types(tmp_path, container, select_base):
    source = tmp_path / 'original.sv'
    source.write_text(source_text(container), encoding='utf-8')
    output = tmp_path / 'generated'
    suffix = '.lane[0]' if container == 'generate' else ''
    targets = (['SharedBase'] if select_base else []) + ['tb.*' + suffix + '.Driver']
    arguments = ['export', '--class', *targets, '--sv-source', str(source), '--out', str(output)]
    main(arguments, out=io.StringIO())
    before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in output.rglob('*') if path.is_file()}
    main([*arguments, '--check'], out=io.StringIO())
    assert before == {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in output.rglob('*') if path.is_file()}
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(manifest['classes']) == 3 + int(select_base)
    for cls in manifest['classes']:
        if cls['symbol'] == 'Driver':
            assert [base['canonical_id'] for base in cls['base_lineage']] == ['sv://unit/0/SharedBase']
    driver_module = instance_public_module('tb.a' + suffix)
    if not select_base:
        # Required nested value types are exported, not a callable base mirror.
        assert 'class SharedBase(' not in (output / 'python/svx_mirror_unit/unit_0.py').read_text(encoding='utf-8')
        return
    program = f'''
import importlib
from svx import _native, inheritance
from {driver_module} import Driver
from svx_mirror_unit.unit_0 import SharedBase
assert Driver.__bases__ == (SharedBase,)
assert 'count' not in Driver.__dict__
assert inheritance._python_subclasses.get('sv://unit/0/SharedBase') in (None, SharedBase)
allocations = []
def create(class_id, payload):
    allocations.append(class_id)
    return 817
_native.inheritance_create_sv = create
_native.inheritance_bind = lambda *args: None
_native.inheritance_close = lambda *args: None
importlib.import_module({driver_module!r}).encode_constructor = lambda class_id, values: values
driver = Driver(23)
assert isinstance(driver, SharedBase)
assert len(allocations) == 1
assert allocations[0] == Driver.__svx_foreign_class_id__
assert driver._svx_remote_object_id == 817
class UserDriver(Driver):
    pass
assert inheritance._python_subclasses[Driver.__svx_foreign_class_id__] is UserDriver
assert inheritance._python_subclasses.get('sv://unit/0/SharedBase') in (None, SharedBase)
print('LEXICAL_ANCESTRY_IMPORT_PASS')
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=os.pathsep.join([str(output / 'python'), *sys.path]))
    result = subprocess.run([sys.executable, '-c', program], env=env, text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0 and 'LEXICAL_ANCESTRY_IMPORT_PASS' in result.stdout, result.stdout + result.stderr


def test_generate_descendant_preserves_selected_outer_owner_base(tmp_path):
    text = source_text('generate')
    base, marker, remainder = text.partition('module lexical_owner #(int W=8);')
    assert marker
    source = tmp_path / 'original.sv'
    source.write_text(marker + '\n' + base + remainder, encoding='utf-8')
    output = tmp_path / 'generated'
    arguments = ['export', '--class', 'tb.*.SharedBase', 'tb.*.lane[0].Driver',
                 '--sv-source', str(source), '--out', str(output)]
    main(arguments, out=io.StringIO())
    main([*arguments, '--check'], out=io.StringIO())
    program = f'''
from {instance_public_module('tb.a')} import SharedBase as Base_a
from {instance_public_module('tb.b')} import SharedBase as Base_b
from {instance_public_module('tb.a.lane[0]')} import Driver
assert Driver.__bases__ == (Base_a,)
assert not issubclass(Driver, Base_b)
assert Driver.State is Base_a.State
assert 'count' not in Driver.__dict__
print('OUTER_ANCESTRY_PASS')
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=os.pathsep.join([str(output / 'python'), *sys.path]))
    result = subprocess.run([sys.executable, '-c', program], env=env, text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0 and 'OUTER_ANCESTRY_PASS' in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize('use_inner', [False, True])
def test_shadowed_outer_nominal_names_are_not_silently_rebound(tmp_path, use_inner):
    source = tmp_path / 'original.sv'
    text = '''module owner;
  typedef enum bit[3:0] {ROOT=0} Mode;
  class Base;
    Mode root_state;
    function new(); root_state=ROOT; endfunction
  endclass
  for(genvar i=0;i<1;i++)begin:lane
    typedef enum bit[7:0] {LEAF=0} Mode;
    class Derived extends Base;
      Mode local_state;
      function new(); super.new();local_state=LEAF;endfunction
    endclass
  end
endmodule
module tb;owner a();endmodule
'''
    if not use_inner:
        text = text.replace('      Mode local_state;\n', '').replace('local_state=LEAF;', '')
    source.write_text(text, encoding='utf-8')
    output = tmp_path / 'generated'
    with pytest.raises(SVXInheritanceError, match='shadowed native names'):
        main(['export', '--class', 'tb.a.lane[0].Derived', '--sv-source', str(source),
              '--out', str(output)], out=io.StringIO())
    assert not (output / 'artifacts.json').exists()
    assert not (output / 'python').exists()
    assert not (output / 'sv').exists()
    assert source.read_text(encoding='utf-8') == text


def test_exact_generate_target_discovers_only_its_required_outer_ancestry(tmp_path):
    text = source_text('generate')
    base, marker, remainder = text.partition('module lexical_owner #(int W=8);')
    source = tmp_path / 'original.sv'
    source.write_text(marker + '\n' + base + remainder, encoding='utf-8')
    output = tmp_path / 'generated'
    arguments = ['export', '--class', 'tb.a.lane[0].Driver', '--sv-source', str(source), '--out', str(output)]
    main(arguments, out=io.StringIO())
    main([*arguments, '--check'], out=io.StringIO())
    manifest = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert len(manifest['classes']) == 1
    assert manifest['classes'][0]['base_lineage'][0]['canonical_id'] == 'sv://instance/tb/a/class/SharedBase'
    assert {value['source_scope']['path'] for value in manifest['value_types']} == {'tb.a', 'tb.a.lane[0]'}
