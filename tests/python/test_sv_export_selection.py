import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from svx.cli import main
from svx.declarations import manifest_from_declarations
from svx.errors import SVXInheritanceError


pytest.importorskip('pyslang')


@pytest.fixture
def project(tmp_path):
    source = tmp_path / 'project.sv'
    source.write_text('''
package base_pkg;
  class Base;
    int seed;
    function new(int seed); this.seed = seed; endfunction
    virtual function int status(); return seed; endfunction
  endclass
  class NotSelected; endclass
endpackage
package drivers;
  import base_pkg::*;
  class Driver extends Base;
    function new(int seed); super.new(seed); endfunction
    function int status(); return super.status() + 1; endfunction
    function void adjust(input int value, output int old_value, inout int total);
      old_value=seed; seed=value; total+=value;
    endfunction
  endclass
  class Other; endclass
endpackage
package facade;
  import drivers::Driver;
  export drivers::Driver;
  class Own; endclass
endpackage
''', encoding='utf-8')
    filelist = tmp_path / 'design.f'
    filelist.write_text('project.sv\n', encoding='utf-8')
    return source, filelist


def test_direct_class_discovers_members_and_lineage_without_python_or_json(project):
    source, _ = project
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['drivers::Driver'])
    assert [item.symbol for item in manifest.classes] == ['drivers::Driver']
    target = manifest.classes[0]
    assert target.constructor.initiator == 'python'
    assert [item.name for item in target.constructor.parameters] == ['seed']
    assert [item.symbol for item in target.base_lineage] == ['base_pkg::Base']
    assert any(method.name == 'status' and method.virtual for method in target.methods)
    adjust = next(method for method in target.methods if method.name == 'adjust')
    assert [parameter.direction for parameter in adjust.parameters] == ['input', 'output', 'inout']


@pytest.mark.parametrize('first_module', ['base_pkg', 'drivers', 'same_package', 'mixed', 'mixed_integrated'])
def test_selected_packages_preserve_python_inheritance_and_one_constructor(project, tmp_path, first_module):
    source, _ = project
    driver_module = 'drivers'
    packages = ['base_pkg', 'drivers']
    extra_arguments = []
    if first_module in {'mixed', 'mixed_integrated'}:
        integrated = first_module == 'mixed_integrated'
        first_module = 'drivers'
        extra_arguments = ['--python-module', 'tests.integration.package_export_independent']
        if integrated:
            extra_arguments.append('--integrated')
    if first_module == 'same_package':
        text = source.read_text(encoding='utf-8').replace(
            'endpackage\npackage drivers;\n  import base_pkg::*;', '')
        # The facade import is unrelated to this test's selected declarations.
        text = text[:text.index('package facade;')]
        source.write_text(text, encoding='utf-8')
        driver_module = first_module = 'base_pkg'
        packages = ['base_pkg']
    root = tmp_path / 'generated'
    arguments = ['export', *extra_arguments, '--package', *packages, '--sv-source', str(source),
                 '--out', str(root)]
    if extra_arguments:
        environment = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
        generation = subprocess.run([sys.executable, '-m', 'svx', *arguments], env=environment,
                                    capture_output=True, text=True, timeout=60)
        assert generation.returncode == 0, generation.stdout + generation.stderr
        artifact = json.loads((root / 'artifacts.json').read_text(encoding='utf-8'))
        assert artifact['systemverilog_startup'] == 'svx_exports_pkg::initialize'
    else:
        assert main(arguments, out=io.StringIO()) == 0
    program = f'''
import importlib
from svx import inheritance, _native
importlib.import_module('svx_mirror.{first_module}')
from svx_mirror.base_pkg import Base
from svx_mirror.{driver_module} import Driver
assert issubclass(Driver, Base)
assert Driver.__bases__ == (Base,)
namespace = {{}}
exec('from svx_mirror.{driver_module} import *', namespace)
assert namespace['Driver'] is Driver
assert 'Driver' in dir(importlib.import_module('svx_mirror.{driver_module}'))
assert inheritance._python_subclasses.get('sv://base_pkg/Base') in (None, Base)
allocations = []
def create(class_id, payload):
    allocations.append((class_id, payload))
    return 817
_native.inheritance_create_sv = create
_native.inheritance_bind = lambda object_id, instance: None
_native.inheritance_close = lambda object_id: None
inheritance.encode_constructor = lambda class_id, values: values
# Generated modules capture encode_constructor during module import.
importlib.import_module('svx_mirror.{driver_module}').encode_constructor = inheritance.encode_constructor
driver = Driver(23)
assert isinstance(driver, Base)
assert allocations == [('sv://{driver_module}/Driver', {{'seed': 23}})], allocations
assert driver._svx_remote_object_id == 817
class UserDriver(Driver):
    pass
assert inheritance._python_subclasses['sv://{driver_module}/Driver'] is UserDriver
assert inheritance._python_subclasses.get('sv://base_pkg/Base') in (None, Base)
print('PACKAGE_INHERITANCE_PASS')
'''
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(root / 'python'), *sys.path])
    result = subprocess.run([sys.executable, '-c', program], env=env, text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('package, expected', [
    ('drivers', ['drivers::Driver', 'drivers::Other']),
    ('facade', ['facade::Own']),
])
def test_package_exports_owned_classes_not_imported_or_reexported_classes(project, package, expected):
    source, _ = project
    manifest = manifest_from_declarations(sv_source_files=[source], sv_package_targets=[package])
    assert [item.symbol for item in manifest.classes] == expected


def test_recursive_package_selection_is_explicit_and_exclusions_apply(project):
    source, _ = project
    manifest = manifest_from_declarations(
        sv_source_files=[source], sv_package_targets=['facade'], sv_recursive_packages=True,
        sv_exclude_classes=['*::Other', '*::NotSelected'])
    assert [item.symbol for item in manifest.classes] == ['base_pkg::Base', 'drivers::Driver', 'facade::Own']


def test_repeated_patterns_are_deterministic_and_deduplicated(project):
    source, _ = project
    manifest = manifest_from_declarations(
        sv_source_files=[source], sv_class_targets=['drivers::*', 'sv://drivers/Driver'],
        sv_package_targets=['drivers'], sv_exclude_classes=['drivers::Other'])
    assert [item.symbol for item in manifest.classes] == ['drivers::Driver']


def test_member_selection_handles_inherited_methods_without_exporting_fields(project):
    source, _ = project
    manifest = manifest_from_declarations(
        sv_source_files=[source], sv_class_targets=['drivers::Driver'], sv_member_targets=['status'])
    target = manifest.classes[0]
    assert [method.name for method in target.methods] == ['status']
    assert [method.name for method in target.base_lineage[0].methods] == ['status']
    assert not target.fields and not target.base_lineage[0].fields


def test_explicit_member_exclusion_and_unknown_member_diagnostic(project):
    source, _ = project
    manifest = manifest_from_declarations(
        sv_source_files=[source], sv_class_targets=['drivers::Driver'],
        sv_exclude_members=['adjust', 'base_pkg::Base.seed'])
    assert [method.name for method in manifest.classes[0].methods] == ['status']
    assert not manifest.classes[0].base_lineage[0].fields
    with pytest.raises(SVXInheritanceError, match='member selector.*matched no accessible'):
        manifest_from_declarations(sv_source_files=[source], sv_class_targets=['drivers::Driver'],
                                   sv_member_targets=['typo'])


@pytest.mark.parametrize('kwargs, message', [
    ({'sv_class_targets': ['missing::Driver']}, 'class selector.*matched no'),
    ({'sv_package_targets': ['missing']}, 'package selector.*matched no'),
    ({'sv_package_targets': ['drivers'], 'sv_exclude_classes': ['*']}, 'contains no classes'),
    ({'sv_recursive_packages': True}, 'requires a package selector'),
])
def test_invalid_selection_reports_input_problem(project, kwargs, message):
    source, _ = project
    with pytest.raises(SVXInheritanceError, match=message):
        manifest_from_declarations(sv_source_files=[source], **kwargs)


def test_export_reuses_original_filelist_and_generators(project, tmp_path):
    source, filelist = project
    root = tmp_path / 'generated output'
    args = ['export', '--class', 'drivers::Driver', '-f', str(filelist),
            '--sv-build-directory', str(tmp_path), '--out', str(root)]
    out = io.StringIO()
    assert main(args, out=out) == 0
    assert 'from svx_mirror.drivers import Driver' in out.getvalue()
    assert (root / 'python/svx_mirror/drivers.py').is_file()
    assert (root / 'mirrors.sv').is_file()
    assert (root / 'artifacts.json').is_file()
    data = json.loads((root / 'inheritance.json').read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['classes']] == ['drivers::Driver']
    evidence = json.loads((root / 'inheritance.json.svx-discovery.json').read_text(encoding='utf-8'))
    assert evidence['configuration']['sv_selection']['classes'] == ['drivers::Driver']
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in root.rglob('*') if path.is_file()}
    assert main(args + ['--check'], out=io.StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}
    source.write_text(source.read_text(encoding='utf-8').replace(' + 1', ' + 2'), encoding='utf-8')
    with pytest.raises(SystemExit, match='provenance is stale'):
        main(args + ['--check'], out=io.StringIO())
    assert main(args, out=io.StringIO()) == 0
    for path in (root / 'mirrors.sv', root / 'python/svx_mirror/drivers.py'):
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before[path]


def test_invalid_direct_target_does_not_publish_files(project, tmp_path):
    source, _ = project
    root = tmp_path / 'generated'
    with pytest.raises(SVXInheritanceError, match='matched no package, compilation-unit or instance class'):
        main(['export', '--class', 'missing::Class', '--sv-source', str(source),
              '--out', str(root)], out=io.StringIO())
    assert not root.exists()


def test_short_class_names_and_grouped_cli_selection(project, tmp_path):
    source, filelist = project
    target = tmp_path / 'selected.json'
    assert main(['inheritance-manifest', '--class', 'Driver', 'drivers::Other',
                 '--member', 'status', 'adjust', '-f', str(filelist),
                 '--sv-build-directory', str(tmp_path), '--out', str(target)], out=io.StringIO()) == 0
    data = json.loads(target.read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['classes']] == ['drivers::Driver', 'drivers::Other']
    source.write_text(source.read_text(encoding='utf-8') +
                      '\npackage another; class Driver; endclass endpackage', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match='ambiguous SV class.*another::Driver.*drivers::Driver'):
        manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'])


def test_public_example_uses_direct_class_selection(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / 'generated'
    assert main(['export', '--class', 'export_driver_pkg::Driver',
                 '-f', str(root / 'examples/sv_export/design.f'),
                 '--sv-build-directory', str(root), '--out', str(output)], out=io.StringIO()) == 0
    assert (output / 'python/svx_mirror/export_driver_pkg.py').is_file()
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert [item['symbol'] for item in data['classes']] == ['export_driver_pkg::Driver']
    assert data['classes'][0]['base_lineage'][0]['symbol'] == 'export_base_pkg::Base'


def test_native_class_type_parameter_does_not_become_remote_ref(tmp_path):
    from svx.inheritance import emit_sv_mirrors

    source = tmp_path / 'specialization.sv'
    source.write_text('''package configs;
class Config; int setting; endclass
class SpecialConfig extends Config; endclass
endpackage
package drivers;
import configs::*;
class Base #(type CFG=Config);
  CFG cfg;
  function int status(); return cfg.setting; endfunction
endclass
class Middle #(type CFG=Config) extends Base#(CFG); endclass
class Driver extends Middle#(SpecialConfig); endclass
endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source],
        sv_class_targets=['drivers::Driver'], sv_member_targets=['status'])
    for ancestor in manifest.classes[0].base_lineage:
        argument = ancestor.specialization.arguments[0]
        assert argument.type_binding.sv == 'configs::SpecialConfig'
    generated = emit_sv_mirrors(manifest)
    assert 'drivers::Base#(configs::SpecialConfig)' in generated
    assert 'drivers::Base#(svtypes_pkg::remote_ref)' not in generated


def test_comments_are_not_part_of_exported_names_or_directions(tmp_path):
    source = tmp_path / 'documented.sv'
    source.write_text('''package /* package documentation */ documented;
class /* class documentation */ Driver;
int /* field documentation */ count;
function new(int /* constructor argument */ seed); count=seed; endfunction
virtual function int /* method documentation */ status(
  input int /* input documentation */ value,
  // documentation for the following output
  output int result);
  result=count; return value;
endfunction
endclass endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'])
    target = manifest.classes[0]
    assert target.symbol == 'documented::Driver'
    assert [field.name for field in target.fields] == ['count']
    assert target.constructor.parameters[0].name == 'seed'
    method = target.methods[0]
    assert method.name == 'status' and method.virtual
    assert [(parameter.name, parameter.direction) for parameter in method.parameters] == [('value', 'input'), ('result', 'output')]
