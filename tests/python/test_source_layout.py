import json
import os
from pathlib import Path, PurePosixPath
import sys
import subprocess
from types import ModuleType

import pytest

from svx import runtime
from svx.errors import SVXInheritanceError
from svx.inheritance import artifact_manifest, emit_sv_mirrors, parse_manifest
from svx.source_layout import _emit_sv_root_source_unit
from tests.integration.same_package_schema import emit_sources, manifest_data


SOURCE = Path(__file__).parents[1] / 'integration' / 'same_package_source.sv'


@pytest.mark.parametrize('options, message', [
    (['--sv-out', 'a.sv', '--sv-integrated-dir', 'integrated'], 'only one'),
    (['--sv-stage-dir', 'stages', '--sv-integrated-dir', 'integrated'], 'only one'),
    (['--sv-integrated-dir', 'integrated'], 'requires --sv-source'),
    (['--check', '--sv-integrated-dir', 'integrated', '--sv-source', 'one.sv'],
     '--check requires'),
])
def test_invalid_output_configuration_rejects_before_loading_inputs(tmp_path, options, message):
    from io import StringIO
    from svx.cli import main

    manifest = tmp_path / 'invalid.json'
    manifest.write_text('{invalid JSON')
    before = manifest.stat()
    with pytest.raises(SystemExit, match=message):
        main(['inheritance-gen', '--manifest', str(manifest), *options], StringIO())
    assert manifest.read_text() == '{invalid JSON'
    assert manifest.stat().st_mtime_ns == before.st_mtime_ns
    assert list(tmp_path.iterdir()) == [manifest]


def test_integrated_cli_generates_checks_and_preserves_unchanged_outputs(tmp_path):
    from io import StringIO
    from svx.cli import main
    from svx.declarations import manifest_dict
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, source = manifest_and_source(endpoint_handles=True, independent_targets=True)
    source = (SOURCE.parent / 'external_bus_if.sv').read_text() + '\n' + source
    manifest_path = tmp_path / 'manifest.json'
    source_path = tmp_path / 'input.sv'
    manifest_path.write_text(json.dumps(manifest_dict(model)))
    source_path.write_text(source)
    args = ['inheritance-gen', '--manifest', str(manifest_path),
            '--sv-source', str(source_path), '--sv-integrated-dir', str(tmp_path / 'sv'),
            '--python-out', str(tmp_path / 'python'),
            '--artifact-manifest', str(tmp_path / 'artifacts.json')]
    assert main(args, StringIO()) == 0
    generated = tmp_path / 'sv' / 'source.sv'
    assert 'class IndependentLaterImpl extends mixed_source_pkg::_svx_proxy_Independent;' in generated.read_text()
    assert source_path.read_text() == source
    assert generated.read_text().count('package svx_call_records_pkg;') == 1
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
              for path in tmp_path.rglob('*') if path.is_file()}
    assert main(args + ['--check'], StringIO()) == 0
    assert main(args, StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
                      for path in tmp_path.rglob('*') if path.is_file()}
    source_path.write_text(source.replace('return value + 5;', 'return value + 6;'))
    with pytest.raises(SystemExit, match='stale'):
        main(args + ['--check'], StringIO())
    assert generated.read_bytes() == before[generated][0]
    assert main(args, StringIO()) == 0
    assert main(args + ['--check'], StringIO()) == 0
    assert 'return value + 6;' in generated.read_text()


def test_integrated_cli_tracks_shared_macro_source_and_configuration(tmp_path):
    from io import StringIO
    from svx.cli import main
    from svx.declarations import manifest_dict
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, source = manifest_and_source(independent_targets=True)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(manifest_dict(model)))
    prefix = tmp_path / 'prefix.sv'
    prefix.write_text('`define INDEPENDENT_PROXY svx_proxy_python_unit_source::Independent\n')
    owner = tmp_path / 'owner.sv'
    owner.write_text(source.replace('svx_proxy_python_unit_source::Independent', '`INDEPENDENT_PROXY'))
    artifact = tmp_path / 'artifacts.json'
    args = ['inheritance-gen', '--manifest', str(manifest),
            '--sv-source', str(prefix), '--sv-source', str(owner), '--sv-compilation-unit',
            '--sv-integrated-dir', str(tmp_path / 'sv'), '--python-out', str(tmp_path / 'python'),
            '--artifact-manifest', str(artifact)]
    assert main(args, StringIO()) == 0
    generated = tmp_path / 'sv' / 'source.sv'
    assert 'class IndependentImpl extends _svx_proxy_Independent;' in generated.read_text()
    assert 'class IndependentLaterImpl extends mixed_source_pkg::_svx_proxy_Independent;' in generated.read_text()
    inputs = json.loads(artifact.read_text())['generation_inputs']
    assert inputs['sv_sources'] == ['prefix.sv', 'owner.sv']
    assert {item['path'] for item in inputs['sv_dependencies']} == {'prefix.sv', 'owner.sv'}
    assert inputs['source_mode'] == 'shared-compilation-unit'
    assert main(args + ['--check'], StringIO()) == 0
    before = (generated.read_bytes(), generated.stat().st_mtime_ns)
    prefix.write_text(prefix.read_text() + '// source option changed\n')
    with pytest.raises(SystemExit, match='prefix.sv'):
        main(args + ['--check'], StringIO())
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == before
    assert main(args, StringIO()) == 0
    with pytest.raises(SystemExit, match='sv_predefines'):
        main(args + ['--sv-define', 'AUDIT_FLAG=1', '--check'], StringIO())
    assert main(args + ['--sv-define', 'AUDIT_FLAG=1'], StringIO()) == 0
    assert main(args + ['--sv-define', 'AUDIT_FLAG=1', '--check'], StringIO()) == 0


@pytest.mark.parametrize('damage', ['user_file', 'duplicate_inventory', 'input_collision'])
def test_integrated_cli_rejects_unsafe_output_without_changes(tmp_path, damage):
    from io import StringIO
    from svx.cli import main
    from svx.declarations import manifest_dict
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, source = manifest_and_source(independent_targets=True)
    source_path = tmp_path / 'inputs' / 'source.sv'
    source_path.parent.mkdir()
    source_path.write_text(source)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest_dict(model)))
    output_root = tmp_path / 'generated'
    args = ['inheritance-gen', '--manifest', str(manifest_path), '--sv-source', str(source_path),
            '--sv-integrated-dir', str(output_root), '--python-out', str(tmp_path / 'python'),
            '--artifact-manifest', str(tmp_path / 'artifacts.json')]
    assert main(args, StringIO()) == 0
    if damage == 'user_file':
        (output_root / 'source.sv').write_text('// user implementation\n')
        message = 'non-generated'
    elif damage == 'duplicate_inventory':
        (output_root / '.svx-generated-sv.json').write_text('["source.sv", "source.sv"]')
        message = 'duplicate'
    else:
        args[args.index('--sv-integrated-dir') + 1] = str(source_path.parent)
        message = 'non-generated|input source'
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
              for path in tmp_path.rglob('*') if path.is_file()}
    with pytest.raises(SVXInheritanceError, match=message):
        main(args, StringIO())
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
                      for path in tmp_path.rglob('*') if path.is_file()}


@pytest.mark.parametrize('shared_module', [False, True])
def test_mixed_source_python_artifacts_preserve_independent_requested_target(shared_module):
    import ast
    from svx.declarations import manifest_dict
    from svx.inheritance import _emit_source_python_artifacts
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, _ = manifest_and_source(endpoint_handles=True)
    data = manifest_dict(model)
    module = 'tests.integration.python_unit_source' if shared_module else 'audit_aux'
    data['classes'].append({
        'canonical_id': 'py://audit/Independent', 'language': 'python',
        'symbol': module + '.Independent', 'methods': [],
        'constructor': {'initiator': 'python', 'parameters': []},
    })
    outputs = _emit_source_python_artifacts(parse_manifest(data))
    path = PurePosixPath('svx_py', *module.split('.')).with_suffix('.py')
    assert path in outputs
    tree = ast.parse(outputs[path])
    assert any(isinstance(node, ast.ClassDef) and node.name == 'Independent' for node in ast.walk(tree))
    if shared_module:
        assert 'def _svx_define_Root' in outputs[path]
        assert 'def _svx_define_Derived' in outputs[path]
    compile(outputs[path], str(path), 'exec')


@pytest.mark.parametrize('shared_module', [False, True])
def test_mixed_source_sv_artifacts_preserve_independent_requested_target(shared_module):
    from pyslang.syntax import SyntaxTree
    from svx.declarations import manifest_dict
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, source = manifest_and_source(endpoint_handles=True)
    data = manifest_dict(model)
    module = 'tests.integration.python_unit_source' if shared_module else 'audit_aux'
    data['classes'].append({
        'canonical_id': 'py://audit/Independent', 'language': 'python',
        'symbol': module + '.Independent', 'methods': [],
        'constructor': {'initiator': 'python', 'parameters': []},
    })
    output = _emit_source_units(parse_manifest(data), {'mixed-source.sv': source})
    package = 'svx_proxy_' + module.split('.')[-1]
    assert output.count('package ' + package + ';') == 1
    assert 'virtual class Independent implements' in output
    assert 'class IndependentFactory #(type Implementation = Independent)' in output
    assert 'typedef mixed_source_pkg::_svx_proxy_Root Root;' in output
    assert output.count('package svx_external_handles_pkg;') == 1
    assert output.count('sv_class: mixed_source_pkg::Packet') == 1
    assert not list(SyntaxTree.fromText(output).diagnostics)


def test_independent_sv_mirror_uses_its_matching_public_factory_protocol():
    import ast
    from svx.inheritance import _emit_source_python_artifacts
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, _ = manifest_and_source(endpoint_handles=True, independent_targets=True)
    output = _emit_source_python_artifacts(model)[PurePosixPath('svx_mirror/mixed_source_pkg.py')]
    node = next(node for node in ast.parse(output).body
                if isinstance(node, ast.ClassDef) and node.name == 'Pure')
    text = ast.get_source_segment(output, node)
    assert '_create_sv_with_direct_mirror(' not in text
    assert '.inheritance_create_sv(' in text
    assert '__svx_direct_mirror_field_ids__' not in text


@pytest.mark.parametrize('collision', [False, True])
def test_independent_python_proxy_precedes_source_consumer(collision):
    from pyslang.syntax import SyntaxTree
    from svx.declarations import manifest_dict
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, source = manifest_and_source(endpoint_handles=True)
    data = manifest_dict(model)
    data['classes'].append({
        'canonical_id': 'py://audit/Independent', 'language': 'python',
        'symbol': 'tests.integration.python_unit_source.Independent', 'methods': [],
        'constructor': {'initiator': 'python', 'parameters': []},
    })
    if collision:
        source = source.replace('package mixed_source_pkg;',
                                'package mixed_source_pkg; class _svx_proxy_Independent; endclass')
    source = source.replace('endpackage\n',
                            'class Impl extends svx_proxy_python_unit_source::Independent; endclass\nendpackage\n')
    source += ('package later_pkg;\n'
               'class LaterImpl extends svx_proxy_python_unit_source::Independent; endclass\n'
               'endpackage\n')
    output = _emit_source_units(parse_manifest(data), {'mixed-source.sv': source})
    private = 'svx__svx_proxy_Independent' if collision else '_svx_proxy_Independent'
    assert 'class Impl extends ' + private + ';' in output
    assert output.index('virtual class ' + private + ' implements') < output.index('class Impl extends')
    assert 'typedef mixed_source_pkg::' + private + ' Independent;' in output
    assert 'class LaterImpl extends mixed_source_pkg::' + private + ';' in output
    assert output.count('virtual class ' + private + ' implements') == 1
    assert output.count('package svx_proxy_python_unit_source;') == 1
    assert not list(SyntaxTree.fromText(output).diagnostics)


def test_independent_sv_target_without_source_declaration_is_rejected():
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, _ = manifest_and_source(endpoint_handles=True, independent_targets=True)
    _, source = manifest_and_source(endpoint_handles=True)
    with pytest.raises(SVXInheritanceError, match='lacks required declaration mixed_source_pkg::Pure'):
        _emit_source_units(model, {'mixed-source.sv': source})


def test_source_unit_external_endpoint_can_use_existing_forward_class_typedef():
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, original = manifest_and_source(endpoint_handles=True, forward_endpoint_type=True)
    text = _emit_source_units(model, {'mixed-source.sv': original})
    assert text.index('typedef class Packet;') < text.index('sv_class: mixed_source_pkg::Packet')
    assert text.index('sv_class: mixed_source_pkg::Packet') < text.index('class C extends')
    assert text.index('class C extends') < text.index('class Packet; int value; endclass')


def test_source_unit_external_endpoint_still_rejects_type_without_forward_declaration():
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    model, original = manifest_and_source(endpoint_handles=True, forward_endpoint_type=True)
    original = original.replace('typedef class Packet;', '')
    with pytest.raises(SVXInheritanceError, match='source type declared after its consumer'):
        _emit_source_units(model, {'mixed-source.sv': original})


@pytest.mark.parametrize('macro', [False, True])
def test_source_unit_early_public_endpoint_reference_uses_ready_owner(macro):
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source, endpoint_source_inputs

    model, source = manifest_and_source(endpoint_handles=True, multiple_endpoint_packages=True)
    inputs = endpoint_source_inputs(source)
    public = 'svx_external_handles_pkg::SVXExternal_sv___mixed_source_pkg_Packet'
    consumer = inputs['early-endpoint-consumer.sv']
    consumer = consumer.replace('  import svtypes_pkg::*;',
                                '  import svtypes_pkg::*;\n  // ' + public + '\n'
                                '  localparam string label = "' + public + '";')
    if macro:
        consumer = consumer.replace(public + '::encode(null)', '`ENDPOINT_TYPE::encode(null)')
        consumer = '`define ENDPOINT_TYPE ' + public + '\n' + consumer
    inputs['early-endpoint-consumer.sv'] = consumer
    text = _emit_source_units(model, inputs)
    early = text[text.index('module early_endpoint_consumer;'):text.index('endmodule', text.index('module early_endpoint_consumer;'))]
    assert 'endpoint_types_pkg::_svx_SVXExternal_sv___mixed_source_pkg_Packet::encode(null)' in early
    assert 'svx_external_handles_pkg::SVXExternal_sv___mixed_source_pkg_Packet::encode(null)' not in early
    assert text.count('sv_class: endpoint_types_pkg::Packet') == 1
    assert '// ' + public in text
    assert '"' + public + '"' in text
    if macro:
        assert '`define ENDPOINT_TYPE ' + public in text


@pytest.mark.parametrize('collision', [False, True])
def test_source_unit_automatically_owns_external_endpoints_once(collision):
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source
    from pyslang.syntax import SyntaxTree

    manifest, original = manifest_and_source(endpoint_handles=True)
    if collision:
        original = original.replace('package mixed_source_pkg;',
                                    'package mixed_source_pkg; class _svx_SVXExternal_sv___mixed_source_pkg_Packet; endclass')
    text = _emit_source_units(manifest, {'mixed-source.sv': original})
    assert text.count('package svx_external_handles_pkg;') == 1
    assert text.count('sv_class: mixed_source_pkg::Packet <-> RemoteRef') == 1
    assert text.count('virtual_interface: virtual external_bus_if.master <-> RemoteRef') == 1
    assert text.index('endclass\n') < text.index('sv_class: mixed_source_pkg::Packet')
    assert 'mixed_source_pkg::_svx_SVXExternal_sv_vif___external_bus_if_master::decode' in text
    assert 'typedef mixed_source_pkg::' in text
    assert not list(SyntaxTree.fromText(text).diagnostics)
    if collision:
        assert text.count('class _svx_SVXExternal_sv___mixed_source_pkg_Packet;') == 1
        assert 'typedef mixed_source_pkg::_svx_SVXExternal_sv___mixed_source_pkg_Packet SVXExternal_' not in text


def test_source_unit_external_endpoint_follows_static_type_alias():
    from svx.declarations import manifest_dict
    from svx.source_layout import _emit_source_units
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    manifest, original = manifest_and_source(endpoint_handles=True)
    data = manifest_dict(manifest)
    def alias(value):
        if isinstance(value, dict):
            if value.get('sv_type') == 'mixed_source_pkg::Packet':
                value['sv_type'] = 'mixed_source_pkg::packet_alias_t'
            for item in value.values():
                alias(item)
        elif isinstance(value, list):
            for item in value:
                alias(item)
    alias(data)
    original = original.replace('class Packet; int value; endclass',
                                'class Packet; int value; endclass\n  typedef Packet packet_alias_t;')
    text = _emit_source_units(parse_manifest(data), {'mixed-source.sv': original})
    assert text.index('typedef Packet packet_alias_t;') < text.index('sv_class: mixed_source_pkg::packet_alias_t')
    assert text.count('sv_class: mixed_source_pkg::packet_alias_t') == 1


def test_inline_external_adapter_renderer_uses_one_owner_and_selected_binding():
    from svx.inheritance import _emit_sv_external_handle_adapters, _manifest_handle_bindings
    from tests.integration.constructor_handles_schema import manifest_data as handle_manifest
    from tests.integration.inline_endpoint_schema import emit_sources as inline_sources

    model = parse_manifest(handle_manifest())
    binding = next(item for item in _manifest_handle_bindings(model) if item.kind == 'sv_class')
    lines = _emit_sv_external_handle_adapters(model, package_name=None, bindings=(binding,))
    assert not any(line.startswith('package ') or line.startswith('endpackage') for line in lines)
    text = '\n'.join(lines)
    assert text.count('class SVXExternal_sv___external_handle_test_pkg_PacketEndpoint implements') == 1
    assert 'virtual external_bus_if' not in text
    original = '\n'.join(_emit_sv_external_handle_adapters(model))
    assert 'package svx_external_handles_pkg;' in original
    assert 'endpackage : svx_external_handles_pkg' in original
    source = inline_sources()['source.sv']
    assert source.count('class SVXExternal_sv___external_handle_test_pkg_PacketEndpoint implements') == 1
    assert source.count('class SVXExternal_sv_vif___external_bus_if_masterEndpoint implements') == 1
    assert source.count('typedef external_handle_test_pkg::SVXExternal_') == 4


def test_source_unit_rewrites_proxy_member_and_method_type_references():
    manifest = parse_manifest(manifest_data())
    original = SOURCE.read_text()
    original = original.replace('    int extra = 100;', '''    svx_proxy_same_package_test::B peer;
    function svx_proxy_same_package_test::B identity(svx_proxy_same_package_test::B value);
      return value;
    endfunction
    localparam string proxy_name = "svx_proxy_same_package_test::B";
    int extra = 100;''')
    text = _emit_sv_root_source_unit(manifest, original)
    assert '    _svx_proxy_B peer;' in text
    assert 'function _svx_proxy_B identity(_svx_proxy_B value);' in text
    assert '"svx_proxy_same_package_test::B"' in text
    assert '// class C extends svx_proxy_same_package_test::B' in text


def test_source_unit_forward_proxy_handles_get_forward_class_declaration():
    original = SOURCE.read_text().replace('package same_package_pkg;', '''package same_package_pkg;
  class Holder;
    svx_proxy_same_package_test::B peer;
  endclass''')
    text = _emit_sv_root_source_unit(parse_manifest(manifest_data()), original)
    assert text.index('typedef class _svx_proxy_B;') < text.index('class Holder;')
    assert '_svx_proxy_B peer;' in text
    assert text.count('typedef class _svx_proxy_B;') == 1


@pytest.mark.parametrize('root_assembler', ['mixed', 'python'])
def test_mixed_root_python_artifacts_include_python_root_vif_views(monkeypatch, root_assembler):
    from svx import inheritance
    from svx.inheritance import _emit_source_python_artifacts, _emit_python_root_artifacts
    from tests.integration.constructor_handles_schema import manifest_data as handle_manifest
    from tests.integration.python_unit_schema import manifest_data as python_manifest
    import svtypes

    data = manifest_data()
    other = python_manifest()
    field = handle_manifest()['classes'][0]['fields'][1]

    def add_vif(source):
        if source['canonical_id'].endswith('/Root'):
            source.setdefault('fields', []).append(field)
        for ancestor in source.get('base_lineage', []):
            add_vif(ancestor)

    for source in other['classes']:
        add_vif(source)
    data['classes'] += other['classes']
    model = parse_manifest(data)
    artifacts = (_emit_source_python_artifacts(model) if root_assembler == 'mixed' else
                 _emit_python_root_artifacts(model, source_managed_layout=True))
    path = PurePosixPath('svx_vif/external_bus_if/master.py')
    assert path in artifacts
    monkeypatch.setattr(inheritance, '_vif_views', {})
    namespace = {}
    exec(compile(artifacts[path], str(path), 'exec'), namespace)
    reference = svtypes.RemoteRefValue('sv-vif://external_bus_if/master', 731)
    value = inheritance._decode_vif_view(reference)
    assert isinstance(value, namespace['Master'])
    assert callable(value.read) and callable(value.write_data)
    assert inheritance._encode_vif_view(value) == reference
    with pytest.raises(TypeError, match='target does not match'):
        namespace['Master'](svtypes.RemoteRefValue('sv-vif://other/master', 731))


@pytest.mark.parametrize('macro', [False, True])
def test_source_unit_proxy_static_reference_preserves_non_owner_references(macro):
    from tests.integration.python_unit_schema import manifest_data as python_manifest
    from svx.source_layout import _emit_python_root_source_unit

    original = (SOURCE.parent / 'python_unit_source.sv').read_text()
    name = '`PROXY_TYPE' if macro else 'svx_proxy_python_unit_source::Root'
    original = original.replace('  class Child extends svx_proxy_python_unit_source::Root;',
                                '  class Child extends svx_proxy_python_unit_source::Root;\n'
                                f'    function int explicit_scale(int value); return {name}::scale(value); endfunction')
    if macro:
        original = '`define PROXY_TYPE svx_proxy_python_unit_source::Root\n' + original
    original += 'module consumer; svx_proxy_python_unit_source::Root value; endmodule\n'
    text = _emit_python_root_source_unit(parse_manifest(python_manifest()), original)
    assert 'return _svx_proxy_Root::scale(value);' in text
    assert 'module consumer; svx_proxy_python_unit_source::Root value; endmodule' in text
    if macro:
        assert '`define PROXY_TYPE svx_proxy_python_unit_source::Root' in text


def test_python_root_source_unit_registers_static_dispatch_without_source_allocation():
    from tests.integration.python_unit_schema import emit_sources

    _manifest, _python, sv = emit_sources()
    source = sv[PurePosixPath('source.sv')]
    assert 'virtual class _svx_proxy_Root_static_gateway;' in source
    assert 'register_static("py://tests/integration/python_unit/Root", this)' in source
    assert '_svx_proxy_Root::scale(' in source
    assert '_svx_proxy_Root::wait_once(' in source
    assert '_svx_proxy_Root_static_dispatch _svx_proxy_Root_static_instance = new();' in source
    assert 'virtual class _svx_proxy_Root_static_gateway extends' not in source


def test_mixed_root_source_unit_integrates_both_families_in_one_package():
    from tests.integration.mixed_source_unit_schema import manifest_and_source
    from svx.source_layout import _emit_source_units

    manifest, source = manifest_and_source()
    output = _emit_source_units(manifest, {'mixed-source.sv': source})
    assert 'class C extends _svx_proxy_B;' in output
    assert 'class Child extends _svx_proxy_Root;' in output
    assert 'class Grandchild extends _svx_proxy_Derived;' in output
    assert 'typedef mixed_source_pkg::_svx_proxy_B B;' in output
    assert 'typedef mixed_source_pkg::_svx_proxy_Root Root;' in output
    assert 'typedef mixed_source_pkg::_svx_proxy_Derived Derived;' in output
    assert output.count('package mixed_source_pkg;') == 1
    assert source == manifest_and_source()[1]


@pytest.mark.parametrize('root_language', ['sv', 'python'])
def test_unified_source_unit_matches_existing_single_root_layout(root_language):
    from svx.source_layout import _emit_source_units, _emit_sv_root_source_units, _emit_python_root_source_units

    if root_language == 'sv':
        manifest = parse_manifest(manifest_data())
        source = SOURCE.read_text()
        emitter = _emit_sv_root_source_units
    else:
        from tests.integration.python_unit_schema import manifest_data as python_data
        manifest = parse_manifest(python_data())
        source = Path('tests/integration/python_unit_source.sv').read_text()
        emitter = _emit_python_root_source_units
    inputs = {'source.sv': source}
    assert _emit_source_units(manifest, inputs) == emitter(manifest, inputs)


def test_mixed_root_source_layout_is_independent_of_requested_target_order():
    from dataclasses import replace
    from tests.integration.mixed_source_unit_schema import manifest_and_source
    from svx.source_layout import _emit_source_units

    manifest, source = manifest_and_source()
    inputs = {'mixed-source.sv': source}
    reversed_manifest = replace(manifest, classes=tuple(reversed(manifest.classes)))
    assert _emit_source_units(manifest, inputs) == _emit_source_units(reversed_manifest, inputs)


def test_source_copy_integrates_same_package_without_changing_public_names():
    original = SOURCE.read_bytes()
    manifest, python, sv = emit_sources()
    assert SOURCE.read_bytes() == original
    integrated = sv[PurePosixPath('source.sv')]
    assert integrated == _emit_sv_root_source_unit(manifest, original.decode())
    assert 'class C extends _svx_proxy_B;' in integrated
    assert '// class C extends svx_proxy_same_package_test::B' in integrated
    assert 'typedef same_package_pkg::_svx_proxy_B B;' in integrated
    assert 'typedef same_package_pkg::_svx_mirror_A A;' in integrated
    assert 'typedef same_package_pkg::_svx_mirror_C C;' in integrated
    assert integrated.index('package svx_proxy_same_package_test;') > integrated.index('endpackage\n')
    view = python[PurePosixPath('svx_mirror/same_package_pkg.py')]
    assert 'class A(SVMirror):' in view and '    class C(_RootCompanion):' in view
    assert "C.__qualname__ = 'C'" in view
    assert 'def _svx_finalize_generated_types():' in view
    metadata = artifact_manifest(manifest, python, sv_sources=sv)
    types = {entry['canonical_class_id']: entry for entry in metadata['generated_types']}
    assert types['sv://same_package_pkg/C']['python_fqn'] == 'svx_mirror.same_package_pkg.C'
    assert types['py://tests/integration/same_package/B']['systemverilog_fqn'] == 'svx_proxy_same_package_test::B'
    for path, text in python.items():
        compile(text, str(path), 'exec')
    with pytest.raises(SVXInheritanceError, match='declaration cycle'):
        emit_sv_mirrors(manifest)


def test_source_offsets_preserve_unicode_comments_and_avoid_private_name_collisions():
    source = '// \u7c7b\u7ee7\u627f\u6ce8\u91ca\n' + SOURCE.read_text()
    source = source.replace('  class A;', '  class _svx_mirror_A; endclass\n  class A;')
    source = source.replace('  class C extends', '  string spelling = "svx_proxy_same_package_test::B";\n  class C extends')
    manifest = parse_manifest(manifest_data())
    output = _emit_sv_root_source_unit(manifest, source)
    assert output.startswith('// \u7c7b\u7ee7\u627f\u6ce8\u91ca\n')
    assert 'class _svx_mirror_A; endclass' in output
    assert 'class svx__svx_mirror_A extends same_package_pkg::A' in output
    assert 'string spelling = "svx_proxy_same_package_test::B";' in output
    assert 'class C extends _svx_proxy_B;' in output


def test_aliases_precede_downstream_source_consumers():
    source = SOURCE.read_text() + '\nmodule source_consumer; svx_proxy_same_package_test::B value; endmodule\n'
    output = _emit_sv_root_source_unit(parse_manifest(manifest_data()), source)
    assert output.index('package svx_proxy_same_package_test;') < output.index('module source_consumer;')
    assert output.endswith('module source_consumer; svx_proxy_same_package_test::B value; endmodule\n')


@pytest.mark.parametrize('root_language', ['sv', 'python'])
def test_named_units_resolve_headers_relative_to_each_source_directory(tmp_path, root_language):
    from svx.source_layout import _emit_sv_root_source_units, _emit_python_root_source_units

    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    (first / 'settings.svh').write_text('localparam int FIRST = 11;\n')
    (second / 'settings.svh').write_text('localparam int SECOND = 22;\n')
    first_source = 'package first_pkg;\n`include "settings.svh"\nendpackage\n'
    second_source = 'package second_pkg;\n`include "settings.svh"\nendpackage\n'
    if root_language == 'python':
        from tests.integration.python_unit_schema import manifest_data as python_manifest
        manifest = parse_manifest(python_manifest())
        design = Path('tests/integration/python_unit_source.sv').read_text()
        emit = _emit_python_root_source_units
    else:
        manifest = parse_manifest(manifest_data())
        design = SOURCE.read_text()
        emit = _emit_sv_root_source_units
    inputs = {str(first / 'source.sv'): first_source,
              str(second / 'source.sv'): second_source,
              str(tmp_path / 'design.sv'): design}
    output = emit(manifest, inputs)
    assert output.index('FIRST = 11') < output.index('package second_pkg;')
    assert output.index('SECOND = 22') > output.index('package second_pkg;')
    assert ('class C extends _svx_proxy_B;' if root_language == 'sv'
            else 'class Child extends _svx_proxy_Root;') in output
    assert str(first / 'settings.svh') in output
    assert str(second / 'settings.svh') in output


def test_nested_include_class_anchors_keep_source_locations_and_macro_state(tmp_path):
    from pyslang import SourceManager
    from pyslang.syntax import SyntaxTree
    from svx.source_layout import _emit_sv_root_source_units

    original = SOURCE.read_text()
    base, derived = original.split('  // The tool must not rewrite', 1)
    base = base.split('package same_package_pkg;\n', 1)[1]
    derived = '  // The tool must not rewrite' + derived.rsplit('endpackage', 1)[0]
    nested = tmp_path / 'nested'
    nested.mkdir()
    base_header = tmp_path / 'base.svh'
    derived_header = nested / 'derived.svh'
    container = tmp_path / 'classes.svh'
    base_header.write_text('`define SOURCE_EXTRA 100\n' + base)
    derived_header.write_text('// \u7c7b\u6ce8\u91ca\n' + derived.replace('extra = 100', 'extra = `SOURCE_EXTRA'))
    container.write_text('`include "base.svh"\n`include "nested/derived.svh"\n')
    before = {path: path.read_bytes() for path in (base_header, derived_header, container)}
    source = 'package same_package_pkg;\n`include "classes.svh"\nendpackage\n'
    output = _emit_sv_root_source_units(parse_manifest(manifest_data()),
                                       {'design.sv': source}, include_dirs=iter([tmp_path]))
    assert 'class C extends _svx_proxy_B;' in output
    assert 'extra = `SOURCE_EXTRA' in output
    assert '// \u7c7b\u6ce8\u91ca' in output
    assert all(path.read_bytes() == text for path, text in before.items())
    manager = SourceManager()
    tree = SyntaxTree.fromText(output, manager)
    locations = {}

    def visit(node):
        if type(node).__name__ == 'ClassDeclarationSyntax' and str(node.name).strip() in {'A', 'C'}:
            locations[str(node.name).strip()] = (Path(str(manager.getFileName(node.sourceRange.start))).resolve(),
                                                manager.getLineNumber(node.sourceRange.start))

    tree.root.visit(visit)
    assert locations['A'] == (base_header, 2)
    assert locations['C'] == (derived_header, 4)


def test_included_source_keeps_inactive_branches_and_repeated_header_guards(tmp_path):
    from svx.source_layout import _emit_sv_root_source_units

    header = tmp_path / 'guarded.svh'
    header.write_text('`ifndef SOURCE_ONCE\n`define SOURCE_ONCE\n' + SOURCE.read_text() + '\n`endif\n')
    source = ('`ifdef NEVER_SELECTED\n`include "missing.svh"\n`endif\n'
              '`include "guarded.svh"\n`include "guarded.svh"\n')
    output = _emit_sv_root_source_units(parse_manifest(manifest_data()),
                                       {'design.sv': source}, include_dirs=[tmp_path])
    assert '`include "missing.svh"' in output
    assert output.count('class _svx_mirror_A extends') == 1
    assert output.count('class _svx_proxy_B extends') == 1
    assert output.count('package svx_proxy_same_package_test;') == 1


def test_tracked_nested_include_fixture_integrates_without_editing_inputs():
    paths = sorted(Path('tests/integration').glob('same_package_include_*'))
    before = {path: path.read_bytes() for path in paths}
    _, _, outputs = emit_sources(Path('tests/integration/same_package_include_source.sv').read_text())
    assert 'class C extends _svx_proxy_B;' in outputs[PurePosixPath('source.sv')]
    assert all(path.read_bytes() == contents for path, contents in before.items())


def test_include_materialization_preserves_file_and_line_macros(tmp_path, monkeypatch):
    from pyslang import SourceManager
    from pyslang.syntax import SyntaxTree
    from svx.source_layout import _inline_active_source_includes

    monkeypatch.chdir(tmp_path)
    Path('values.svh').write_text('string included_file = `__FILE__;\nint included_line = `__LINE__;\n')
    source = ('`line 20 "logical-source.sv" 0\npackage locations;\n'
              '`include "values.svh"\nstring resumed_file = `__FILE__;\n'
              'int resumed_line = `__LINE__;\nendpackage\n')
    before = SyntaxTree.fromText(source, SourceManager())
    after = SyntaxTree.fromText(_inline_active_source_includes(before, source), SourceManager())

    def values(tree):
        found = {}
        def visit(node):
            if type(node).__name__ == 'DeclaratorSyntax':
                found[str(node.name).strip()] = str(node.initializer).strip()
        tree.root.visit(visit)
        return found

    assert values(before) == values(after)
    assert 'values.svh' in values(after)['included_file']
    assert 'logical-source.sv' in values(after)['resumed_file']


def test_single_text_source_keeps_line_macros_after_helper_insertion():
    from pyslang import SourceManager
    from pyslang.syntax import SyntaxTree

    source = SOURCE.read_text().replace('    int extra = 100;',
        '    int extra = 100;\n    localparam int user_line = `__LINE__;')
    before = SyntaxTree.fromText(source, SourceManager())
    output = _emit_sv_root_source_unit(parse_manifest(manifest_data()), source)
    after = SyntaxTree.fromText(output, SourceManager())

    def value(tree):
        found = []
        def visit(node):
            if type(node).__name__ == 'DeclaratorSyntax' and str(node.name).strip() == 'user_line':
                found.append(str(node.initializer).strip())
        tree.root.visit(visit)
        assert len(found) == 1
        return found[0]

    assert value(before) == value(after)


@pytest.mark.parametrize('python_root', [False, True])
def test_transparent_constructor_enters_context_in_default_parameter_not_local_initializer(python_root):
    import re
    if python_root:
        from tests.integration.python_unit_schema import emit_sources as emit_python
        _, _, sources = emit_python()
    else:
        _, _, sources = emit_sources()
    source = sources[PurePosixPath('source.sv')]
    assert 'typedef svx_pkg::svx_construction_context __svx_construction_context_type;' in source
    assert re.search(r'input bit \w+ = __svx_construction_context_type::enter\(\w+, this\)', source)
    assert not re.search(r'^\s+bit \w+ = \w+::enter', source, re.MULTILINE)
    assert '__svx_construction_context_type::leave(this,' in source


def test_python_root_supports_package_anchors_in_an_include():
    from svx.source_layout import _emit_python_root_source_unit
    from tests.integration.python_unit_schema import manifest_data as python_manifest

    path = Path('tests/integration/python_unit_source.sv')
    before = path.read_bytes()
    source = Path('tests/integration/python_unit_include_source.sv').read_text()
    output = _emit_python_root_source_unit(parse_manifest(python_manifest()), source)
    assert 'class Child extends _svx_proxy_Root;' in output
    assert 'class Grandchild extends _svx_proxy_Derived;' in output
    assert 'typedef python_unit_pkg::_svx_proxy_Root Root;' in output
    assert 'typedef python_unit_pkg::_svx_proxy_Derived Derived;' in output
    assert path.read_bytes() == before


@pytest.mark.parametrize('definition,invocation', [
    ('`define HEADER "classes.svh"', '`HEADER'),
    ('`define INNER "classes.svh"\n`define HEADER `INNER', '`HEADER'),
    ('`define HEADER(NAME) NAME', '`HEADER("classes.svh")'),
])
def test_source_include_filename_macros_use_physical_invocation_span(tmp_path, definition, invocation):
    from svx.source_layout import _emit_sv_root_source_units

    header = tmp_path / 'classes.svh'
    header.write_text(SOURCE.read_text())
    original = header.read_bytes()
    source = definition + '\n`include ' + invocation + '\n'
    output = _emit_sv_root_source_units(parse_manifest(manifest_data()),
                                       {'design.sv': source}, include_dirs=[tmp_path])
    assert 'class C extends _svx_proxy_B;' in output
    assert output.startswith('`line 1 "design.sv" 0\n' + definition + '\n')
    assert '`include ' + invocation not in output
    assert header.read_bytes() == original


@pytest.mark.parametrize('edit, message', [
    (lambda text: text.replace('class C extends', 'class Other extends'), 'lacks required declaration'),
    (lambda text: text.replace('svx_proxy_same_package_test::B;', 'WrongBase;'), 'declared Python proxy'),
    (lambda text: text.replace('endpackage', 'endpackage\npackage same_package_pkg; endpackage'), 'duplicate source package'),
])
def test_source_integration_rejects_invalid_anchors_without_partial_output(edit, message):
    manifest = parse_manifest(manifest_data())
    source = edit(SOURCE.read_text())
    with pytest.raises(SVXInheritanceError, match=message):
        _emit_sv_root_source_unit(manifest, source)
    assert SOURCE.read_text() != source


@pytest.mark.parametrize('definition, invocation', [
    ('`define PROXY_TYPE svx_proxy_same_package_test::B', '`PROXY_TYPE'),
    ('`define INNER svx_proxy_same_package_test::B\n`define PROXY_TYPE `INNER', '`PROXY_TYPE'),
    ('`define PROXY_TYPE(PACKAGE, NAME) PACKAGE::NAME', '`PROXY_TYPE(svx_proxy_same_package_test, B)'),
])
def test_base_macro_rewrites_invocation_not_definition_or_other_uses(definition, invocation):
    source = definition + '\n' + SOURCE.read_text().replace(
        'extends svx_proxy_same_package_test::B;', 'extends ' + invocation + ';')
    source += '\nmodule consumer; ' + invocation + ' handle; endmodule\n'
    output = _emit_sv_root_source_unit(parse_manifest(manifest_data()), source)
    assert output.startswith(definition + '\n')
    assert 'class C extends _svx_proxy_B;' in output
    assert output.endswith('module consumer; ' + invocation + ' handle; endmodule\n')


@pytest.mark.parametrize('definition, invocation', [
    ('`define PROXY_TYPE svx_proxy_same_package_test::B; int extra_from_macro', '`PROXY_TYPE'),
    ('`define PROXY_TYPE(TYPE) TYPE; int extra_from_macro', '`PROXY_TYPE(svx_proxy_same_package_test::B)'),
])
def test_base_macro_cannot_discard_additional_generated_members(definition, invocation):
    source = definition + '\n' + SOURCE.read_text().replace(
        'extends svx_proxy_same_package_test::B;', 'extends ' + invocation + ';')
    with pytest.raises(SVXInheritanceError, match='base macro must expand only'):
        _emit_sv_root_source_unit(parse_manifest(manifest_data()), source)


def test_artifact_loader_finalizes_deferred_views_only_after_all_module_imports(tmp_path, monkeypatch):
    manifest, python, sv = emit_sources()
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources=sv)
    for relative, text in {**{PurePosixPath('python') / path: text for path, text in python.items()}, **sv}.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    path = tmp_path / 'artifacts.json'
    path.write_text(json.dumps(metadata))
    expected = [entry['module'] for entry in metadata['artifacts'] if entry['language'] == 'python']
    events = []
    capabilities = runtime._read_svtypes_capabilities()

    def import_module(name):
        events.append(name)
        module = ModuleType(name)
        if name == 'svx_mirror.same_package_pkg':
            def finalize():
                assert events == expected
                events.append('finalized')
            module._svx_finalize_generated_types = finalize
        return module

    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.setattr(runtime.importlib, 'import_module', import_module)
    runtime._load_artifact_manifest(path, capabilities)
    assert events == [*expected, 'finalized']


@pytest.mark.parametrize('source_first', [False, True])
def test_shared_source_import_orders_keep_one_complete_type_graph(tmp_path, source_first):
    manifest, python, sv = emit_sources(shared_module=True)
    for path, text in python.items():
        output = tmp_path / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    for path, text in sv.items():
        (tmp_path / path).write_text(text)
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources=sv)
    (tmp_path / 'artifacts.json').write_text(json.dumps(metadata))
    view = python[PurePosixPath('svx_mirror/same_package_pkg.py')]
    assert '\nclass C(' not in view and '\nclass E(' not in view
    assert '\nclass A(SVMirror):' in view
    program = f'''
import importlib
from pathlib import Path
from svx import runtime, inheritance
if {source_first!r}:
    import tests.integration.same_module_source
runtime._load_artifact_manifest(Path({str(tmp_path / 'artifacts.json')!r}), runtime._read_svtypes_capabilities())
from tests.integration.same_module_source import B, D
from svx_mirror.same_package_pkg import C, E
from svx_py.tests.integration.same_module_source import B as BC, D as DC
assert D.__bases__ == (C, B)
assert issubclass(C, BC) and issubclass(E, DC)
for cls, key in [(C, 'sv://same_package_pkg/C'), (E, 'sv://same_package_pkg/E'),
                 (BC, 'py://tests/integration/same_package/B'), (DC, 'py://tests/integration/same_package/D')]:
    assert inheritance._python_subclasses[key] is cls
    assert cls.__qualname__ == cls.__name__
module = importlib.import_module('svx_py.tests.integration.same_module_source')
assert module.__getattr__('B') is BC and module.__getattr__('D') is DC
runtime._load_artifact_manifest(Path({str(tmp_path / 'artifacts.json')!r}), runtime._read_svtypes_capabilities())
assert inheritance._python_subclasses['sv://same_package_pkg/C'] is C
'''
    repo = Path(__file__).parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (
        tmp_path / 'python', repo / 'python', repo.parent / 'svtypes' / 'python', repo))))
    result = subprocess.run([sys.executable, '-c', program], cwd=repo, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_ordered_source_inputs_preserve_locations_and_publish_aliases_when_ready():
    from pyslang import SourceManager
    from pyslang.syntax import SyntaxTree
    from tests.integration.multi_unit_schema import emit_sources as emit_multi, source_inputs

    original = source_inputs()
    manifest, python, sv = emit_multi()
    assert source_inputs() == original
    assert [target.name for target in manifest.classes] == ['E']
    text = sv[PurePosixPath('source.sv')]
    assert text.index('package svx_mirror_sv_multi_a_pkg_A;') < text.index('module multi_early_consumer;')
    assert text.count('package svx_proxy_multi_unit_source;') == 1
    assert 'typedef multi_c_pkg::_svx_proxy_B B;' in text
    assert 'typedef multi_e_pkg::_svx_proxy_D D;' in text
    manager = SourceManager()
    tree = SyntaxTree.fromText(text, manager)
    found = {}

    def visit(node):
        if type(node).__name__ == 'ClassDeclarationSyntax' and str(node.name).strip() in {'A', 'C', 'E'}:
            found[str(node.name).strip()] = (str(manager.getFileName(node.sourceRange.start)), manager.getLineNumber(node.sourceRange.start))

    tree.root.visit(visit)
    assert found == {name: (f'tests/integration/multi_{name.lower()}_source.sv', 2) for name in ('A', 'C', 'E')}
    for path, source in python.items():
        compile(source, str(path), 'exec')


def test_source_input_order_keeps_shared_preprocessor_state():
    from tests.integration.multi_unit_schema import manifest_data as multi_manifest, source_inputs
    from svx.source_layout import _emit_sv_root_source_units

    inputs = source_inputs()
    first, source = next(iter(inputs.items()))
    inputs[first] = '`define INCLUDE_BASE\n`ifdef INCLUDE_BASE\n' + source + '`endif\n'
    # A define from one source remains visible to the next source in this unit.
    inputs['tests/integration/multi_c_source.sv'] = '`ifdef INCLUDE_BASE\n' + inputs['tests/integration/multi_c_source.sv'] + '`endif\n'
    output = _emit_sv_root_source_units(parse_manifest(multi_manifest()), inputs)
    assert '`ifdef INCLUDE_BASE' in output
    assert 'class C extends _svx_proxy_B;' in output


@pytest.mark.parametrize('inputs', [{}, {'bad\nname.sv': ''}, {'source.sv': 1}])
def test_multi_source_input_validation(inputs):
    from svx.source_layout import _join_source_units

    with pytest.raises((SVXInheritanceError, TypeError)):
        _join_source_units(inputs)


def test_compile_predefines_select_anchors_and_explicit_undefines_remove_them():
    from tests.integration.multi_unit_schema import manifest_data as multi_manifest, source_inputs
    from svx.source_layout import _emit_sv_root_source_units

    manifest = parse_manifest(multi_manifest())
    inputs = source_inputs(configured=True)
    before = dict(inputs)
    output = _emit_sv_root_source_units(manifest, inputs, predefines={'SVX_MULTI_ENABLED': '1'})
    assert 'class _svx_mirror_A extends multi_a_pkg::A' in output
    assert '`ifdef SVX_MULTI_ENABLED' in output
    assert '`define SVX_MULTI_ENABLED' not in output
    for options in ({}, {'predefines': {'SVX_MULTI_ENABLED': '1'}, 'undefines': ('SVX_MULTI_ENABLED',)}):
        with pytest.raises(SVXInheritanceError, match='lacks required declaration multi_a_pkg::A'):
            _emit_sv_root_source_units(manifest, inputs, **options)
    assert _emit_sv_root_source_units(manifest, inputs, predefines={'SVX_MULTI_ENABLED': '1'}) == output
    assert inputs == before


@pytest.mark.parametrize('predefines,undefines', [
    ([], ()), ({'bad-name': '1'}, ()), ({'VALID': 1}, ()),
    ({'VALID': '1\n`define OTHER'}, ()), (None, 'VALID'), (None, ('bad-name',)),
])
def test_compile_macro_options_reject_ambiguous_or_invalid_input(predefines, undefines):
    from svx.source_layout import _source_parse_options

    with pytest.raises((SVXInheritanceError, TypeError)):
        _source_parse_options(predefines, undefines)


@pytest.mark.parametrize('source_first', [False, True])
def test_python_root_multi_inputs_preserve_import_identity_and_source_order(tmp_path, source_first):
    from tests.integration.python_multi_unit_schema import emit_sources as emit_multi, source_inputs

    original = source_inputs()
    manifest, python, sv = emit_multi()
    assert source_inputs() == original
    assert [target.name for target in manifest.classes] == ['Grandchild']
    text = sv[PurePosixPath('source.sv')]
    assert text.index('package svx_mirror_sv_python_unit_pkg_Child;') < text.index('module python_multi_consumer;')
    assert text.count('package svx_proxy_python_unit_source;') == 1
    assert 'typedef python_unit_pkg::_svx_proxy_Root Root;' in text
    assert 'typedef python_multi_final_pkg::_svx_proxy_Derived Derived;' in text
    for path, source in python.items():
        output = tmp_path / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source)
    for path, source in sv.items():
        (tmp_path / path).write_text(source)
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources=sv)
    (tmp_path / 'artifacts.json').write_text(json.dumps(metadata))
    program = f'''
from pathlib import Path
from svx import runtime, inheritance
if {source_first!r}:
    import tests.integration.python_unit_source
path = Path({str(tmp_path / 'artifacts.json')!r})
runtime._load_artifact_manifest(path, runtime._read_svtypes_capabilities())
from tests.integration.python_unit_source import Root, Derived
from svx_mirror.python_unit_pkg import Child
from svx_mirror.python_multi_final_pkg import Grandchild
from svx_py.tests.integration.python_unit_source import Root as RC, Derived as DC
assert Derived.__bases__ == (Child, Root)
assert issubclass(Child, RC) and issubclass(Grandchild, DC)
assert Grandchild.__module__ == 'svx_mirror.python_multi_final_pkg'
for cls, key in [(Child, 'sv://python_unit_pkg/Child'),
                 (Grandchild, 'sv://python_multi_final_pkg/Grandchild'),
                 (RC, 'py://tests/integration/python_unit/Root'),
                 (DC, 'py://tests/integration/python_unit/Derived')]:
    assert inheritance._python_subclasses[key] is cls
    assert cls.__qualname__ == cls.__name__
runtime._load_artifact_manifest(path, runtime._read_svtypes_capabilities())
assert inheritance._python_subclasses['sv://python_multi_final_pkg/Grandchild'] is Grandchild
'''
    repo = Path(__file__).parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (
        tmp_path / 'python', repo / 'python', repo.parent / 'svtypes' / 'python', repo))))
    result = subprocess.run([sys.executable, '-c', program], cwd=repo, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('source_first', [False, True])
def test_python_root_shared_source_has_unique_types_and_transparent_construction(tmp_path, source_first):
    from tests.integration.python_unit_schema import emit_sources as emit_python_unit

    manifest, python, sv = emit_python_unit()
    integrated = sv[PurePosixPath('source.sv')]
    assert 'class Child extends _svx_proxy_Root;' in integrated
    assert 'class Grandchild extends _svx_proxy_Derived;' in integrated
    assert 'typedef python_unit_pkg::_svx_proxy_Root Root;' in integrated
    assert 'typedef python_unit_pkg::_svx_proxy_Derived Derived;' in integrated
    assert 'super.new(child_seed);' in integrated
    assert 'super.new(e_seed);' in integrated
    assert '__svx_construction_context_type::enter(' in integrated
    assert [cls.name for cls in manifest.classes] == ['Grandchild']
    for path, text in python.items():
        output = tmp_path / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    for path, text in sv.items():
        (tmp_path / path).write_text(text)
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources=sv)
    (tmp_path / 'artifacts.json').write_text(json.dumps(metadata))
    program = f'''
from pathlib import Path
from svx import runtime, inheritance
if {source_first!r}:
    import tests.integration.python_unit_source
path = Path({str(tmp_path / 'artifacts.json')!r})
runtime._load_artifact_manifest(path, runtime._read_svtypes_capabilities())
from tests.integration.python_unit_source import Root, Derived
from svx_mirror.python_unit_pkg import Child, Grandchild
from svx_py.tests.integration.python_unit_source import Root as RC, Derived as DC
assert Derived.__bases__ == (Child, Root)
assert issubclass(Child, RC) and issubclass(Grandchild, DC)
for cls, key in [(Child, 'sv://python_unit_pkg/Child'),
                 (Grandchild, 'sv://python_unit_pkg/Grandchild'),
                 (RC, 'py://tests/integration/python_unit/Root'),
                 (DC, 'py://tests/integration/python_unit/Derived')]:
    assert inheritance._python_subclasses[key] is cls
    assert cls.__qualname__ == cls.__name__
runtime._load_artifact_manifest(path, runtime._read_svtypes_capabilities())
assert inheritance._python_subclasses['sv://python_unit_pkg/Child'] is Child
assert inheritance._python_subclasses['sv://python_unit_pkg/Grandchild'] is Grandchild
'''
    repo = Path(__file__).parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (
        tmp_path / 'python', repo / 'python', repo.parent / 'svtypes' / 'python', repo))))
    result = subprocess.run([sys.executable, '-c', program], cwd=repo, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_mixed_root_python_artifacts_share_one_deferred_module():
    import ast
    from dataclasses import replace
    from svx.inheritance import _emit_source_python_artifacts
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    manifest, _ = manifest_and_source()
    artifacts = _emit_source_python_artifacts(manifest)
    path = PurePosixPath('svx_mirror/mixed_source_pkg.py')
    tree = ast.parse(artifacts[path])
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert functions.count('__getattr__') == 1
    assert functions.count('_svx_finalize_generated_types') == 1
    assert len(functions) == len(set(functions))
    loaders = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name.startswith('_svx_define_')}
    assert {'_svx_define_C', '_svx_define_Child', '_svx_define_Grandchild'} <= loaders.keys()
    assert [node.name for node in tree.body if isinstance(node, ast.ClassDef)].count('A') == 1
    for text in artifacts.values():
        compile(text, '<mixed-generated>', 'exec')
    reversed_manifest = replace(manifest, classes=tuple(reversed(manifest.classes)))
    assert _emit_source_python_artifacts(reversed_manifest) == artifacts


@pytest.mark.parametrize('source_first', [False, True])
def test_mixed_root_python_artifacts_import_both_families(tmp_path, source_first):
    from dataclasses import replace
    from svx.inheritance import _emit_source_python_artifacts
    from tests.integration.mixed_source_unit_schema import manifest_and_source

    manifest, _ = manifest_and_source()

    def relocate(source):
        ancestors = tuple(relocate(item) for item in source.base_lineage)
        if source.language == 'python':
            module = 'mixed_sv_source' if source.name == 'B' else 'mixed_python_source'
            return replace(source, symbol=module + '.' + source.name, base_lineage=ancestors)
        return replace(source, base_lineage=ancestors)

    manifest = replace(manifest, classes=tuple(relocate(source) for source in manifest.classes))
    artifacts = _emit_source_python_artifacts(manifest)
    repo = Path(__file__).parents[2]
    for name, original in [('mixed_sv_source', 'same_package_test'),
                           ('mixed_python_source', 'python_unit_source')]:
        text = (repo / 'tests/integration' / (original + '.py')).read_text()
        text = text.replace('svx_mirror.same_package_pkg', 'svx_mirror.mixed_source_pkg')
        text = text.replace('svx_mirror.python_unit_pkg', 'svx_mirror.mixed_source_pkg')
        (tmp_path / (name + '.py')).write_text(text)
    for path, text in artifacts.items():
        output = tmp_path / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    program = f'''
from svx import inheritance
if {source_first!r}:
    import mixed_sv_source, mixed_python_source
from svx_mirror.mixed_source_pkg import A, C, Child, Grandchild
from svx_py.mixed_sv_source import B as BC
from svx_py.mixed_python_source import Root as RC, Derived as DC
from mixed_sv_source import B
from mixed_python_source import Root, Derived
assert issubclass(B, A) and issubclass(C, BC)
assert issubclass(Child, RC) and issubclass(Grandchild, DC)
assert Derived.__bases__ == (Child, Root)
for cls in [A, C, Child, Grandchild, BC, RC, DC]:
    assert cls.__qualname__ == cls.__name__
import svx_mirror.mixed_source_pkg as module
module._svx_finalize_generated_types()
assert module.C is C and module.Child is Child and module.Grandchild is Grandchild
'''
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (
        tmp_path, repo / 'python', repo.parent / 'svtypes' / 'python', repo))))
    result = subprocess.run([sys.executable, '-c', program], cwd=repo, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
