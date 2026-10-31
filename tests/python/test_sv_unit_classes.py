import json
import io
from pathlib import PurePosixPath

import pytest

from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest
from svx.unit_exports import emit_unit_export_bridge
from svx.sv_scan import scan_sv_sources, validate_sv_declarations
from svx.cli import main

pytest.importorskip('pyslang')


def unit_manifest(tmp_path, index=0):
    """Obtain checked prototype bindings, then describe their actual unit owner."""
    path = tmp_path / 'prototype.sv'
    path.write_text('''package prototype;
class Driver;
int count;
function new(int seed);count=seed;endfunction
virtual function int status();return count+1;endfunction
task advance(input int value,output int previous,inout int total);
#2ns;previous=count;total+=value;count=value;
endtask
static function int twice(int value);return value*2;endfunction
endclass endpackage''', encoding='utf-8')
    original = manifest_from_declarations(sv_source_files=[path], sv_class_targets=['prototype::Driver'])
    data = manifest_dict(original)
    data.pop('discovery_provenance', None)
    data['schema_version'] = '2.5.0'
    owner = data['classes'][0]
    owner['canonical_id'] = f'sv://unit/{index}/Driver'
    owner['symbol'] = '$unit::Driver'
    owner['source_scope'] = {'kind': 'compilation_unit', 'index': index}
    for method in owner['methods']:
        method['canonical_id'] = owner['canonical_id'] + '#' + method['name']
    return parse_manifest(data)


def test_unit_class_manifest_roundtrip_and_public_module(tmp_path):
    manifest = unit_manifest(tmp_path)
    assert manifest_dict(parse_manifest(manifest_dict(manifest))) == manifest_dict(manifest)
    sources = emit_python_mirrors(manifest)
    assert PurePosixPath('svx_mirror_unit/__init__.py') in sources
    assert PurePosixPath('svx_mirror_unit/unit_0.py') in sources
    assert 'class Driver(SVMirror)' in sources[PurePosixPath('svx_mirror_unit/unit_0.py')]
    assert 'svx_mirror/$unit' not in str(sources)


def test_unit_bridge_retains_native_class_and_local_records(tmp_path):
    manifest = unit_manifest(tmp_path)
    metadata = {}
    source = emit_unit_export_bridge(manifest, 0, metadata=metadata)
    assert 'extends $unit::Driver' in source
    assert 'package ' not in '\n'.join(line for line in source.splitlines() if not line.lstrip().startswith('//'))
    assert 'class SVXCall' in source
    assert 'register_svx_unit_mirror_0_' in source
    assert metadata == {'registration_module': 'svx_unit_exports_0', 'registration_method': 'initialize'}
    assert emit_unit_export_bridge(manifest, 1) == ''
    with pytest.raises(SVXInheritanceError, match='original owner'):
        emit_sv_mirrors(manifest)


@pytest.mark.parametrize('scope', [None, {'kind': 'package', 'index': 0},
                                  {'kind': 'compilation_unit', 'index': True},
                                  {'kind': 'compilation_unit', 'index': -1}])
def test_unit_class_invalid_owner_does_not_look_like_package(tmp_path, scope):
    data = manifest_dict(unit_manifest(tmp_path))
    data['classes'][0]['source_scope'] = scope
    with pytest.raises(SVXInheritanceError, match='scope|symbol'):
        parse_manifest(data)


def test_unit_class_id_cannot_alias_another_owner(tmp_path):
    data = manifest_dict(unit_manifest(tmp_path))
    data['classes'][0]['source_scope']['index'] = 1
    with pytest.raises(SVXInheritanceError, match='canonical_id'):
        parse_manifest(data)


def test_unit_class_discovery_needs_no_prototype_package(tmp_path):
    source = tmp_path / 'driver.sv'
    source.write_text('class Driver;int count;function new(int seed);count=seed;endfunction '
                      'virtual function int status();return count;endfunction endclass', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'])
    target, = manifest.classes
    assert target.symbol == '$unit::Driver' and target.canonical_id == 'sv://unit/0/Driver'
    assert target.source_scope == {'kind': 'compilation_unit', 'index': 0}
    assert manifest.schema_version == '2.5.0'
    data = manifest_dict(manifest)
    data['classes'][0]['constructor']['parameters'][0]['type']['sv'] = 'longint'
    with pytest.raises(SVXInheritanceError, match='does not match source type'):
        validate_sv_declarations(data['classes'], [source])


def test_same_named_unit_classes_require_owner_selection(tmp_path):
    first, second = tmp_path / 'first.sv', tmp_path / 'second.sv'
    first.write_text('class Driver;bit[4:0] count;endclass', encoding='utf-8')
    second.write_text('class Driver;bit[12:0] count;endclass', encoding='utf-8')
    with pytest.raises(SVXInheritanceError, match=r'ambiguous SV class.*\$unit\[0\].*\$unit\[1\]'):
        manifest_from_declarations(sv_source_files=[first, second], sv_class_targets=['$unit::Driver'])
    manifest = manifest_from_declarations(sv_source_files=[first, second], sv_class_targets=['$unit[1]::Driver'])
    target, = manifest.classes
    assert target.canonical_id == 'sv://unit/1/Driver'
    assert target.fields[0].type_binding.sv.replace(' ', '') == 'bit[12:0]'
    both = manifest_from_declarations(sv_source_files=[first, second], sv_class_targets=['$unit::*'])
    assert {item.canonical_id for item in both.classes} == {'sv://unit/0/Driver', 'sv://unit/1/Driver'}


def test_unit_class_lineage_resolves_imported_and_local_bases(tmp_path):
    source = tmp_path / 'classes.sv'
    source.write_text('''package base_pkg;class Base;int inherited;endclass endpackage
import base_pkg::*;
class Middle extends Base;int middle;endclass
class Child extends Middle;int child;endclass
''', encoding='utf-8')
    facts = scan_sv_sources([source], allow_no_packages=True)
    assert facts['$unit[0]::Middle'].direct_base == 'base_pkg::Base'
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Child'])
    target, = manifest.classes
    assert [item.canonical_id for item in target.base_lineage] == ['sv://base_pkg/Base', 'sv://unit/0/Middle']


def test_unit_static_ancestors_register_once_without_becoming_targets(tmp_path):
    source = tmp_path / 'classes.sv'
    source.write_text('''package base_pkg;
class Base;
function new(int seed);endfunction
static function int package_value(int value);return value+1;endfunction
endclass endpackage
class Middle extends base_pkg::Base;
function new(int seed);super.new(seed);endfunction
static function int local_value(int value);return value+2;endfunction
endclass
class Child extends Middle;
function new(int seed);super.new(seed);endfunction
endclass
class Other extends Middle;
function new(int seed);super.new(seed);endfunction
endclass
''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Child', 'Other'])
    assert [item.symbol for item in manifest.classes] == ['$unit::Child', '$unit::Other']
    bridge = emit_unit_export_bridge(manifest, 0)
    for owner in manifest.classes[0].base_lineage:
        registration = 'register_static(' + json.dumps(owner.canonical_id) + ', this)'
        assert bridge.count(registration) == 1
    assert 'extends base_pkg::Base;' in bridge
    assert 'extends $unit::Middle;' in bridge
    assert 'super.new(seed);' in bridge
    assert 'base_pkg::Base::package_value(' in bridge
    assert '$unit::Middle::local_value(' in bridge


def test_shared_unit_discovery_preserves_macros_and_owner(tmp_path):
    first, second = tmp_path / 'prefix.sv', tmp_path / 'driver.sv'
    first.write_text('`define COUNT_WIDTH 13\nclass Base;int inherited;endclass\n', encoding='utf-8')
    second.write_text('class Driver extends Base;bit[`COUNT_WIDTH-1:0] count;endclass', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[first, second],
        sv_class_targets=['Driver'], sv_compilation_unit=True)
    target, = manifest.classes
    assert target.fields[0].type_binding.sv.replace(' ', '') == 'bit[12:0]'
    assert target.base_lineage[0].canonical_id == 'sv://unit/0/Base'


def test_unit_export_cli_automatically_integrates_and_checks(tmp_path):
    source = tmp_path / 'driver.sv'
    source.write_text('class Driver;int count;endclass', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'Driver', '--sv-source', str(source), '--out', str(output), '--incremental']
    message = io.StringIO()
    assert main(args, out=message) == 0
    assert 'from svx_mirror_unit.unit_0 import Driver' in message.getvalue()
    assert 'svx_exports exports()' in message.getvalue()
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['systemverilog_compile_order'] == ['sv/source.sv', 'sv/exports.sv']
    assert artifact['systemverilog_startup_module'] == {'module': 'svx_exports', 'method': 'initialize'}
    assert len(artifact['source_replacements']) == 1
    assert 'extends $unit::Driver' in (output / 'sv/source.sv').read_text(encoding='utf-8')
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in output.rglob('*') if path.is_file()}
    assert main(args + ['--check'], out=io.StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in output.rglob('*') if path.is_file()}


def test_unit_export_independent_replacements_do_not_count_startup_as_original(tmp_path):
    sources = [tmp_path / 'first.sv', tmp_path / 'second.sv']
    for source in sources:
        source.write_text('class Driver;int count;endclass', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', '$unit::*', '--sv-source', str(sources[0]),
            '--sv-source', str(sources[1]), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert len(artifact['source_replacements']) == 2
    assert len(artifact['systemverilog_compile_order']) == 3
    assert artifact['systemverilog_compile_order'][-1] == 'sv/exports.sv'
    assert 'svx_unit_exports_0 unit_0()' in (output / 'sv/exports.sv').read_text(encoding='utf-8')
    assert 'svx_unit_exports_1 unit_1()' in (output / 'sv/exports.sv').read_text(encoding='utf-8')
    assert main(args + ['--check'], out=io.StringIO()) == 0


def test_unit_generic_ancestor_keeps_closed_nondefault_specialization(tmp_path):
    source = tmp_path / 'generic.sv'
    source.write_text('class G#(int W=4);bit[W-1:0] mask;endclass '
                      'class Child extends G#(13);endclass', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Child'])
    parent, = manifest.classes[0].base_lineage
    assert parent.canonical_id.startswith('sv://unit/0/G/specialization/')
    assert parent.specialization.arguments[0].value == 13
    assert parent.fields[0].type_binding.sv.replace(' ', '') == 'bit[12:0]'


def test_unit_records_only_define_their_actual_package_value_dependencies(tmp_path):
    source, later = tmp_path / 'driver.sv', tmp_path / 'later.sv'
    source.write_text('''package values_pkg;typedef enum bit[2:0]{ACTIVE=5} Mode;endpackage
class Driver;
function values_pkg::Mode echo(input values_pkg::Mode mode);return mode;endfunction
endclass''', encoding='utf-8')
    later.write_text('package later_pkg;typedef enum bit[2:0]{IDLE=0} Unused;endpackage\n'
                     'typedef enum bit[1:0]{ON=1} UnitUnused;', encoding='utf-8')
    output = tmp_path / 'generated'
    args = ['export', '--class', 'Driver', '--type', 'later_pkg::Unused', '$unit::UnitUnused',
            '--sv-source', str(source), '--sv-source', str(later), '--out', str(output)]
    assert main(args, out=io.StringIO()) == 0
    text = (output / 'sv/units/000000_driver.sv').read_text(encoding='utf-8')
    assert 'typedef values_pkg::Mode SVXValue_' in text
    assert 'typedef later_pkg::Unused' not in text
    assert 'typedef $unit::UnitUnused' not in text


def test_unit_signature_checks_keep_original_compiler_directives(tmp_path):
    source = tmp_path / 'timed.sv'
    source.write_text('''`timescale 1ps/1ps
package widths;localparam time WIDTH=1ns;endpackage
class Driver;bit[widths::WIDTH-1:0] mask;endclass
''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'])
    assert manifest.classes[0].fields[0].type_binding.sv.replace(' ', '') == 'bit[999:0]'
