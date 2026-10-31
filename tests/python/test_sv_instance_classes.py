import copy
import io
import json
from pathlib import PurePosixPath

import pytest

from svx.declarations import manifest_dict
from svx.cli import main
from svx.errors import SVXInheritanceError
from svx.inheritance import emit_python_mirrors, parse_manifest
from svx.instance_exports import emit_instance_export_bridges
from svx.source_scopes import instance_class_id, instance_namespace_parts
from svx.source_layout import emit_integrated_sources
from svx.sv_frontend import source_elaboration
from test_sv_nested_classes import subprocess_import
from test_sv_unit_classes import unit_manifest


def instance_manifest(tmp_path, path='tb.a', symbol='Driver'):
    data = manifest_dict(unit_manifest(tmp_path))
    data['schema_version'] = '2.6.0'
    source = data['classes'][0]
    source['symbol'] = symbol
    source['source_scope'] = {'kind': 'instance', 'path': path}
    source['canonical_id'] = instance_class_id(path, symbol)
    for method in source['methods']:
        method['canonical_id'] = source['canonical_id'] + '#' + method['name']
    return parse_manifest(data)


def test_instance_manifest_preserves_native_class_and_explicit_owner(tmp_path):
    manifest = instance_manifest(tmp_path)
    data = manifest_dict(manifest)
    assert manifest_dict(parse_manifest(data)) == data
    source, = manifest.classes
    assert source.symbol == 'Driver'
    assert source.canonical_id == 'sv://instance/tb/a/class/Driver'
    assert source.source_scope == {'kind': 'instance', 'path': 'tb.a', 'container': 'module'}


@pytest.mark.parametrize('scope', [
    {'kind': 'instance', 'path': ''}, {'kind': 'instance', 'path': 'tb.a();'},
    {'kind': 'instance', 'path': '$root.tb.a'}, {'kind': 'instance', 'path': 'tb.g[01]'},
    {'kind': 'instance', 'path': 'tb.a', 'index': 0}, {'kind': 'instance', 'path': None},
    {'kind': 'instance', 'path': 'tb.a', 'container': []},
])
def test_instance_scope_rejects_noncanonical_or_unsafe_paths(tmp_path, scope):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['source_scope'] = scope
    with pytest.raises(SVXInheritanceError, match='instance|path|indices'):
        parse_manifest(data)


def test_instance_class_id_cannot_alias_another_binding(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['source_scope']['path'] = 'tb.b'
    with pytest.raises(SVXInheritanceError, match='canonical_id'):
        parse_manifest(data)


def test_instance_backend_binds_original_type_without_copying_source_class(tmp_path):
    manifest = instance_manifest(tmp_path)
    metadata = {}
    text = emit_instance_export_bridges(manifest, metadata=metadata)
    assert 'parameter type SVXSourceType' in text
    assert 'extends SVXSourceType implements' in text
    assert 'bind tb.a ' in text and '.SVXSourceType(Driver)' in text
    assert 'class Driver;' not in text and 'package tb' not in text
    assert 'SVXSourceType::twice(' in text
    assert 'function automatic void initialize();' in text
    assert metadata['instance_bindings'][0]['class_id'] == manifest.classes[0].canonical_id
    assert metadata['instance_bindings'][0]['initialize'].startswith('$root.tb.a.svx_export_')


def test_instance_default_container_and_explicit_container_have_same_lineage_owner(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['base_lineage'] = [{
        'canonical_id': instance_class_id('tb.a', 'Base'), 'language': 'sv', 'symbol': 'Base',
        'source_scope': {'kind': 'instance', 'path': 'tb.a'}, 'methods': [],
    }]
    manifest = parse_manifest(data)
    assert manifest.classes[0].source_scope == manifest.classes[0].base_lineage[0].source_scope
    text = emit_instance_export_bridges(manifest)
    assert 'parameter type SVXBaseType_0' in text and '.SVXBaseType_0(Base)' in text


def test_interface_backend_uses_interface_not_illegal_module_instantiation(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['source_scope']['container'] = 'interface'
    data['classes'][0]['methods'] = [method for method in data['classes'][0]['methods'] if not method.get('static')]
    manifest = parse_manifest(data)
    metadata = {}
    text = emit_instance_export_bridges(manifest, metadata=metadata)
    assert '\ninterface svx_instance_' in text and 'endinterface : svx_instance_' in text
    assert '\nmodule svx_instance_' not in text
    assert metadata['instance_bindings'][0]['bridge_kind'] == 'interface'


def test_interface_static_methods_are_placed_in_original_owner(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['source_scope']['container'] = 'interface'
    with pytest.raises(SVXInheritanceError, match='integrated source copies'):
        emit_instance_export_bridges(parse_manifest(data))
    insertions, metadata = {}, {}
    text = emit_instance_export_bridges(parse_manifest(data), owner_insertions=insertions, metadata=metadata)
    assert 'SVXSourceType::twice(' not in text
    entry, = insertions['tb.a']
    assert 'Driver::twice(' in entry['text']
    assert 'extends Driver' in entry['text']
    assert metadata['instance_bindings'][0]['static_initialize'].endswith(entry['name'] + '.initialize')


def test_program_backend_diagnoses_need_for_legal_in_program_bridge(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['source_scope']['container'] = 'program'
    with pytest.raises(SVXInheritanceError, match='integrated source copies'):
        emit_instance_export_bridges(parse_manifest(data))


def test_instance_scope_checks_real_native_container(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path))
    data['classes'][0]['source_scope']['container'] = 'interface'
    with pytest.raises(SVXInheritanceError, match='does not match native module'):
        emit_integrated_sources(parse_manifest(data), original_sources(tmp_path))


def test_instance_python_packages_support_parent_child_owners_and_nested_classes(tmp_path):
    first = manifest_dict(instance_manifest(tmp_path, 'tb', 'Driver'))
    for path, symbol in (('tb.a', 'Driver'), ('tb.a', 'Outer::Inner')):
        first['classes'].extend(manifest_dict(instance_manifest(tmp_path, path, symbol))['classes'])
    sources = emit_python_mirrors(parse_manifest(first))
    assert PurePosixPath('svx_mirror_instance/tb/__init__.py') in sources
    assert PurePosixPath('svx_mirror_instance/tb/a/__init__.py') in sources
    assert PurePosixPath('svx_mirror_instance/tb.py') not in sources
    assert PurePosixPath('svx_mirror_instance/tb/a.py') not in sources
    output = tmp_path / 'generated'
    for path, text in sources.items():
        destination = output / 'python' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding='utf-8')
    subprocess_import(output, '''from svx_mirror_instance.tb.classes import Driver as Parent
from svx_mirror_instance.tb.a.classes import Driver,Outer
assert Parent is not Driver
assert Driver.__svx_foreign_class_id__=='sv://instance/tb/a/class/Driver'
assert Outer.Inner.__module__=='svx_mirror_instance.tb.a.classes'
assert Outer.Inner.__qualname__=='Outer.Inner'
''')


def test_instance_namespace_indices_and_reserved_prefix_do_not_collide():
    assert instance_namespace_parts('tb.a') == ('tb', 'a')
    paths = ('tb.g[0][1]', 'tb.g_p0[1]', 'tb.svx_scope_1_g_p0_p1',
             'tb.g[-1]', 'tb.lambda', 'tb.svx_scope_id_lambda')
    names = [instance_namespace_parts(path) for path in paths]
    assert len(names) == len(set(names))
    assert all(part.isidentifier() for name in names for part in name)


def test_instance_owner_and_nested_class_boundaries_do_not_collide(tmp_path):
    data = manifest_dict(instance_manifest(tmp_path, 'tb.a', 'Outer::Inner'))
    for owner in ('tb.a.Outer', 'tb.a.classes'):
        data['classes'].extend(manifest_dict(instance_manifest(tmp_path, owner, 'Inner'))['classes'])
    manifest = parse_manifest(data)
    assert len({source.canonical_id for source in manifest.classes}) == 3
    bindings = {}
    emit_instance_export_bridges(manifest, metadata=bindings)
    assert len({item['bridge_module'] for item in bindings['instance_bindings']}) == 3
    sources = emit_python_mirrors(manifest)
    output = tmp_path / 'generated'
    for path, content in sources.items():
        destination = output / 'python' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding='utf-8')
    subprocess_import(output, '''from svx_mirror_instance.tb.a.classes import Outer
from svx_mirror_instance.tb.a.Outer.classes import Inner as Child
from svx_mirror_instance.tb.a.svx_scope_id_classes.classes import Inner as Reserved
assert len({Outer.Inner, Child, Reserved}) == 3
''')


@pytest.mark.parametrize('first,second', [('tb.A', 'tb.a'), ('TB.a', 'tb.b')])
def test_instance_names_reject_filesystem_case_collisions(tmp_path, first, second):
    data = manifest_dict(instance_manifest(tmp_path, first))
    data['classes'].extend(copy.deepcopy(manifest_dict(instance_manifest(tmp_path, second))['classes']))
    with pytest.raises(SVXInheritanceError, match='case-insensitive'):
        parse_manifest(data)


def original_sources(tmp_path):
    source = tmp_path / 'design.sv'
    text = '''module owner;
class Driver;
int count;
function new(int seed);count=seed;endfunction
virtual function int status();return count+1;endfunction
task advance(input int value,output int previous,inout int total);
#2ns;previous=count;total+=value;count=value;endtask
static function int twice(int value);return value*2;endfunction
endclass endmodule
module tb;owner a();endmodule'''
    source.write_text(text, encoding='utf-8')
    return {str(source): text}


def test_instance_source_integration_retains_original_and_links_startup(tmp_path):
    manifest = instance_manifest(tmp_path)
    sources = original_sources(tmp_path)
    metadata = {}
    emitted = emit_integrated_sources(manifest, sources, startup_metadata=metadata)
    assert set(emitted) == {'source.sv', 'exports.sv'}
    assert emitted['source.sv'].count('class Driver;') == 1
    assert 'SVXInstanceMirror' not in emitted['source.sv']
    assert 'bind tb.a ' in emitted['exports.sv']
    assert metadata['systemverilog_startup_module'] == {'module': 'svx_exports', 'method': 'initialize'}
    assert 'initialize_owner(' + json.dumps(metadata['instance_bindings'][0]['initialization_key']) + ');' in emitted['exports.sv']
    assert next(iter(sources.values())) in emitted['source.sv']


def test_instance_source_integration_requires_actual_hierarchy(tmp_path):
    manifest = instance_manifest(tmp_path)
    sources = original_sources(tmp_path)
    with source_elaboration('packages'), pytest.raises(SVXInheritanceError, match='hierarchy elaboration'):
        emit_integrated_sources(manifest, sources)
    absent = instance_manifest(tmp_path, 'tb.absent')
    with pytest.raises(SVXInheritanceError, match='lack required class'):
        emit_integrated_sources(absent, sources)


def test_instance_generation_command_publishes_real_metadata_and_checks_outputs(tmp_path):
    manifest = instance_manifest(tmp_path)
    sources = original_sources(tmp_path)
    output = tmp_path / 'generated'
    path = tmp_path / 'instance.json'
    path.write_text(json.dumps(manifest_dict(manifest)), encoding='utf-8')
    args = ['inheritance-gen', '--manifest', str(path), '--sv-source', next(iter(sources)),
            '--python-out', str(output / 'python'), '--sv-integrated-dir', str(output / 'sv'),
            '--artifact-manifest', str(output / 'artifacts.json')]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    artifact = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifact['generated_types'][0]['python_fqn'] == 'svx_mirror_instance.tb.a.classes.Driver'
    assert artifact['instance_bindings'][0]['instance_path'] == 'tb.a'
    assert len(artifact['source_replacements']) == 1
    assert artifact['systemverilog_compile_order'][-1].endswith('exports.sv')
