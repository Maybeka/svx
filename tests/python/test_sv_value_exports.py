import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import svtypes

from svx.cli import main
from svx.declarations import manifest_dict, manifest_from_declarations
from svx.errors import SVXInheritanceError
from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest
from svx.value_exports import value_modules


pytest.importorskip('pyslang')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'values.sv'
    path.write_text('''package native_values;
  typedef enum bit [7:0] {IDLE=0, RUN=3} State;
  typedef State StateAlias;
  typedef bit [15:0] Word;
  typedef struct packed { State state; Word data; logic [3:0] flags; } Packet;
  class Driver;
    State state;
    Packet packet;
    function new(State initial_state); state=initial_state; endfunction
    function State echo(State value); return value; endfunction
    function Packet echo_packet(Packet value); return value; endfunction
  endclass
endpackage''', encoding='utf-8')
    return path


def test_value_only_manifest_and_normal_import_without_runtime(source, tmp_path):
    output = tmp_path / 'generated'
    args = ['export', '--type', 'native_values::Packet', 'native_values::Word',
            'native_values::StateAlias', '--sv-source', str(source), '--out', str(output)]
    stream = io.StringIO()
    assert main(args, out=stream) == 0
    assert 'from svx_mirror.native_values import Packet' in stream.getvalue()
    data = json.loads((output / 'inheritance.json').read_text(encoding='utf-8'))
    assert data['classes'] == [] and data['schema_version'] == '2.1.0'
    assert {item['symbol'] for item in data['value_types']} == {
        'native_values::State', 'native_values::StateAlias', 'native_values::Word', 'native_values::Packet'}
    assert main(args + ['--check'], out=io.StringIO()) == 0
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([
        str(output / 'python'), str(Path(svtypes.__file__).resolve().parents[1])]))
    result = subprocess.run([sys.executable, '-B', '-c',
        'from svx_mirror.native_values import State, StateAlias, Packet, Word; '
        'assert StateAlias is State; assert Word().width == 16; '
        'p=Packet(); p.state.value=State.RUN; p.data.value=0x1234; '
        'q=Packet(); q.from_bytes(p.to_bytes()); '
        'assert q.state.value == State.RUN and q.data.value==0x1234; '
        'import sys; assert "svx" not in sys.modules; print("VALUE_IMPORT_PASS")'],
        env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'VALUE_IMPORT_PASS' in result.stdout


def test_package_selects_owned_types_and_classes(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_package_targets=['native_values'])
    assert [item.symbol for item in manifest.classes] == ['native_values::Driver']
    assert len(manifest.value_types) == 4
    generated = emit_python_mirrors(manifest)
    text = generated[next(path for path in generated if str(path).endswith('native_values.py'))]
    assert text.index('from _svx_value_types.native_values import') < text.index('class Driver(')
    assert any('class State(' in value for path, value in generated.items() if '_svx_value_types' in str(path))
    assert 'Packet_packer' in emit_sv_mirrors(manifest)


def test_class_signature_automatically_generates_required_values(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['native_values::Driver'])
    assert {item.symbol for item in manifest.value_types} == {'native_values::State', 'native_values::Packet'}
    data = manifest_dict(manifest)
    assert data['classes'][0]['constructor']['parameters'][0]['type']['svtypes']['module'] == 'svx_mirror.native_values'
    assert manifest_dict(parse_manifest(data)) == data


def test_value_modules_are_scoped_and_schema_drift_is_rejected(source):
    before = sys.modules.get('svx_mirror.native_values')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_type_targets=['native_values::State'])
    assert sys.modules.get('svx_mirror.native_values') is before
    with value_modules(manifest.value_types):
        assert 'svx_mirror.native_values' in sys.modules
    assert sys.modules.get('svx_mirror.native_values') is before
    data = manifest_dict(manifest)
    data['value_types'][0]['schema']['width'] = 9
    with pytest.raises(SVXInheritanceError, match='differs from its public SvTypes'):
        parse_manifest(data)
    assert sys.modules.get('svx_mirror.native_values') is before


def test_unknown_type_does_not_publish(source, tmp_path):
    output = tmp_path / 'unknown'
    with pytest.raises(SVXInheritanceError, match='type selector.*matched no'):
        main(['export', '--type', 'Missing', '--sv-source', str(source), '--out', str(output)], out=io.StringIO())
    assert not output.exists()


def test_type_exclusion_cannot_hide_a_required_signature_dependency(source):
    with pytest.raises(SVXInheritanceError, match='requires excluded SV value type.*State'):
        manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'],
                                   sv_exclude_types=['State'])
    manifest = manifest_from_declarations(sv_source_files=[source], sv_package_targets=['native_values'],
        sv_exclude_classes=['Driver'], sv_exclude_types=['Packet', 'Word', 'StateAlias'])
    assert not manifest.classes
    assert [item.symbol for item in manifest.value_types] == ['native_values::State']


def test_codegen_views_preserve_public_identity_and_encoding(source):
    manifest = manifest_from_declarations(sv_source_files=[source], sv_type_targets=['Packet'])
    with value_modules(manifest.value_types, codegen=True) as modules:
        for declaration in manifest.value_types:
            annotation = modules.annotations[declaration.symbol]
            assert svtypes.type_spec_identity(annotation) == declaration.as_dict()['svtypes']
            assert svtypes.schema_descriptor(annotation).to_dict()['schema'] == declaration.as_dict()['schema']
            assert annotation.__name__.startswith('SVXValue_')


def test_cross_package_same_named_types_keep_distinct_public_names(tmp_path):
    source = tmp_path / 'same_names.sv'
    source.write_text('''package first; typedef enum bit [1:0] {A=0,B=1} Mode; endpackage
package second; typedef enum bit [1:0] {A=0,B=2} Mode; endpackage
package consumer; class Driver;
function first::Mode one(first::Mode value); return value; endfunction
function second::Mode two(second::Mode value); return value; endfunction
endclass endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_class_targets=['Driver'])
    assert {item.symbol for item in manifest.value_types} == {'first::Mode', 'second::Mode'}
    text = emit_sv_mirrors(manifest)
    assert 'typedef first::Mode SVXValue_5_first_Mode;' in text
    assert 'typedef second::Mode SVXValue_6_second_Mode;' in text


def test_empty_value_selection_and_malformed_schema_are_actionable(source):
    with pytest.raises(SVXInheritanceError, match='value export selection is empty'):
        manifest_from_declarations(sv_source_files=[source], sv_type_targets=['State'], sv_exclude_types=['*'])
    data = manifest_dict(manifest_from_declarations(sv_source_files=[source], sv_type_targets=['State']))
    del data['value_types'][0]['schema']['items']
    with pytest.raises(SVXInheritanceError, match='invalid public SvTypes value declaration'):
        parse_manifest(data)


def test_value_only_export_skips_unrelated_class_analysis(source, monkeypatch):
    import svx.declarations as declarations

    def unexpected(*args, **kwargs):
        raise AssertionError('value-only export must not analyze classes or VIFs')
    monkeypatch.setattr(declarations, 'scan_sv_sources', unexpected)
    monkeypatch.setattr(declarations, 'scan_sv_virtual_interfaces', unexpected)
    monkeypatch.setattr(declarations, 'validate_sv_declarations', unexpected)
    manifest = manifest_from_declarations(sv_source_files=[source], sv_type_targets=['State'])
    assert not manifest.classes
    assert declarations.enrich_virtual_interface_manifest(manifest, sv_source_files=[source]) is manifest


def test_scalar_and_container_typedef_aliases(tmp_path):
    source = tmp_path / 'containers.sv'
    source.write_text('''package containers;
typedef int Counter;
typedef Counter Fixed[3];
typedef Counter Dynamic[];
typedef Counter Queued[$];
typedef Counter Indexed[string];
endpackage''', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[source], sv_package_targets=['containers'])
    assert len(manifest.value_types) == 5 and not manifest.classes
    generated = emit_python_mirrors(manifest)
    helper = next(text for path, text in generated.items() if str(path) == '_svx_value_types/containers.py')
    assert '.DynArray[' in helper and '.Queue[' in helper and '.AssocArray[' in helper
    with value_modules(manifest.value_types) as modules:
        for name in ('Fixed', 'Dynamic', 'Queued'):
            codec = modules.annotations['containers::' + name]()
            codec.value = [1, 2, 3]
            restored = modules.annotations['containers::' + name]()
            restored.from_bytes(codec.to_bytes())
            assert restored.value == [1, 2, 3]
