import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from svx.cli import main
from svx.declarations import manifest_from_declarations
from svx.errors import SVXInheritanceError
from tests.python.test_sv_constant_exports import import_generated

pytest.importorskip('pyslang')

SOURCE = Path(__file__).parents[1] / 'integration' / 'class_constants.sv'


def export(tmp_path, *selection):
    output = tmp_path / 'generated'
    stream = io.StringIO()
    args = ['export', '--sv-source', str(SOURCE), '--out', str(output), *selection]
    assert main(args, out=stream) == 0
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in output.rglob('*') if path.is_file()}
    assert main([*args, '--check'], out=io.StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in output.rglob('*') if path.is_file()}
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    return output, data, stream.getvalue()


def test_class_constant_only_export_keeps_namespace_types_and_no_runtime(tmp_path):
    output, data, stream = export(tmp_path, '--constant', 'class_constants_pkg::Limits::*')
    assert data['classes'] == []
    assert 'from svx_mirror.class_constants_pkg import Limits' in stream
    assert 'Constant: svx_mirror.class_constants_pkg.Limits.WIDTH' in stream
    assert all(item['symbol'].startswith('class_constants_pkg::Limits::') for item in data['constants'])
    import_generated(output, '''from svx_mirror.class_constants_pkg import Limits
import sys
assert Limits.WIDTH == 8 and Limits.NEGATIVE == -4 and Limits.bytes == 4
assert Limits.DEFAULT_MODE == Limits.Mode.READY
assert Limits.DEFAULT_PACKET.tag.value == 0x91
assert Limits.DEFAULT_PACKET.mode.value == Limits.Mode.READY
assert str(Limits.DEFAULT_PACKET.flags.value) == '10xz'
assert Limits.TABLE == [1, -2, 3]
assert Limits.Nested.LABEL == 'nested' and Limits.Nested.DEPTH == 11
assert 'svx' not in sys.modules
import svx_mirror.class_constants_pkg as package
assert not hasattr(package, 'WIDTH')
assert not isinstance(Limits, type)
''')


def test_package_class_constants_attach_to_real_mirrors_and_preserve_inheritance(tmp_path):
    output, data, _ = export(tmp_path, '--package', 'class_constants_pkg')
    assert data['classes']
    result = subprocess.run([sys.executable, '-B', '-c', '''from svx_mirror.class_constants_pkg import Limits, Derived, Alias
assert isinstance(Limits, type) and isinstance(Derived, type) and isinstance(Alias, type)
assert issubclass(Derived, Limits)
assert Derived.WIDTH == 8 and Derived.COUNT == 16
assert Limits.DEFAULT_MODE == Limits.Mode.READY
assert Alias.WIDTH == Limits.WIDTH
assert Alias.DEFAULT_MODE == Limits.DEFAULT_MODE
assert Alias.DEFAULT_PACKET.mode.value == Limits.Mode.READY
assert Limits.Nested.DEPTH == 11
assert callable(Limits.get_width) and callable(Limits.get_default)
assert callable(Derived.get_value)
for cls in (Limits, Derived, Alias):
    fields = dict(cls._SvObject__svtypes_members)
    assert 'DEFAULT_PACKET' not in fields
    assert 'DEFAULT_MODE' not in fields
'''], env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(output / 'python'), str(SOURCE.parents[2] / 'python'),
        str(SOURCE.parents[2].parent / 'svtypes/python')])),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_constant_alias_and_generated_helper_names_do_not_collide(tmp_path):
    output, _, _ = export(tmp_path, '--constant', 'class_constants_pkg::Alias::*',
                          'class_constants_pkg::_svx_values::*')
    import_generated(output, '''from svx_mirror.class_constants_pkg import Alias, _svx_values
assert Alias.WIDTH == 8
assert Alias.DEFAULT_PACKET.tag.value == 0x91
assert Alias.Nested.LABEL == 'nested'
assert _svx_values.bytes == 7
''')


def test_explicit_inherited_nested_constants_preserve_deferred_class_registration(tmp_path):
    output, _, _ = export(tmp_path, '--class', 'class_constants_pkg::Limits',
        'class_constants_pkg::Derived', 'class_constants_pkg::Alias',
        '--constant', 'class_constants_pkg::Limits::*', 'class_constants_pkg::Derived::*',
        'class_constants_pkg::Alias::*')
    code = '''from svx_mirror.class_constants_pkg import Limits, Derived, Alias
assert issubclass(Derived, Limits)
assert Derived.Nested.DEPTH == Limits.Nested.DEPTH == Alias.Nested.DEPTH == 11
assert Derived.DEFAULT_PACKET.tag.value == 0x91
assert callable(Derived.get_value)
'''
    result = subprocess.run([sys.executable, '-B', '-c', code],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
            str(output / 'python'), str(SOURCE.parents[2] / 'python'),
            str(SOURCE.parents[2].parent / 'svtypes/python')])),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unit_class_constants_keep_compilation_unit_and_nested_namespace(tmp_path):
    output, data, stream = export(tmp_path, '--constant', '$unit::UnitLimits::*')
    assert data['classes'] == []
    assert {item['source_scope']['kind'] for item in data['constants']} == {'compilation_unit'}
    assert 'from svx_mirror_unit.unit_0 import UnitLimits' in stream
    import_generated(output, '''from svx_mirror_unit.unit_0 import UnitLimits
import sys
assert UnitLimits.WIDTH == 12 and UnitLimits.Nested.COUNT == 13
assert 'svx' not in sys.modules
''')


def test_class_constant_short_names_ambiguity_and_exclusions():
    with pytest.raises(SVXInheritanceError, match='ambiguous SV constant.*WIDTH'):
        manifest_from_declarations(sv_source_files=[SOURCE], sv_constant_targets=['WIDTH'])
    model = manifest_from_declarations(sv_source_files=[SOURCE],
        sv_constant_targets=['class_constants_pkg::Limits::*'],
        sv_exclude_constants=['DEFAULT_*', '*::Nested::*'])
    assert {item.name for item in model.constants} == {'WIDTH', 'NEGATIVE', 'TABLE', 'bytes'}


def test_inventory_distinguishes_plain_class_and_generic_constant_owner():
    from svx.sv_inventory import declaration_inventory
    from svx.sv_frontend import source_analysis

    with source_analysis():
        inventory = declaration_inventory([SOURCE], kinds=('constant',))
    declarations = {item['symbol']: item for item in inventory['declarations']}
    assert declarations['class_constants_pkg::Limits::WIDTH']['export_status'] == 'selectable'
    assert declarations['$unit::UnitLimits::WIDTH']['export_status'] == 'selectable'
    assert declarations['generic_constants_pkg::Generic::COUNT']['export_status'] == 'requires-specialization'
