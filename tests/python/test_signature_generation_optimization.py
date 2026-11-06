from copy import deepcopy
from types import SimpleNamespace

import pytest

from svx import inheritance as bridge
from svx.generated_bootstrap import with_bootstrap


@pytest.mark.parametrize('fixture', ['python_root_proxy_schema', 'field_projection_schema',
                                      'constructor_handles_schema', 'alternating_static_schema'])
def test_structured_contracts_preserve_complete_generated_files(fixture):
    import importlib
    data = importlib.import_module('tests.integration.' + fixture).manifest_data()
    manifest = bridge.parse_manifest(data)
    expected = with_bootstrap(bridge._emit_python_mirrors(manifest))
    assert bridge.emit_python_mirrors(manifest) == expected


def test_structured_contract_tokens_do_not_steal_user_names():
    from test_m8_inheritance import manifest_data, INT
    data = manifest_data()
    parameter = '_svx__contract_literal_0'
    data['classes'][0]['methods'][0]['parameters'] = [{'name': parameter, 'type': INT}]
    manifest = bridge.parse_manifest(data)
    assert bridge.emit_python_mirrors(manifest) == with_bootstrap(bridge._emit_python_mirrors(manifest))


def test_signature_probes_are_batched_and_avoid_user_packages(tmp_path, monkeypatch):
    import svx.sv_scan as scan
    from test_sv_signature_types import declaration
    syntax = scan._pyslang()
    texts = []

    def from_text(text, *args, **kwargs):
        if 'svx_signature_probe_' in text:
            texts.append(text)
        return syntax.SyntaxTree.fromText(text, *args, **kwargs)

    monkeypatch.setattr(scan, '_pyslang', lambda: SimpleNamespace(
        SyntaxKind=syntax.SyntaxKind,
        SyntaxTree=SimpleNamespace(fromText=from_text, fromFile=syntax.SyntaxTree.fromFile,
                                   fromFiles=syntax.SyntaxTree.fromFiles)))
    source = tmp_path / 'classes.sv'
    source.write_text('package svx_signature_probe_0; endpackage\npackage p;\n' +
        '\n'.join(f'class A{i}; function int check(input int value); return value; endfunction endclass'
                  for i in range(24)) + '\nendpackage')
    declarations = []
    for i in range(24):
        item = declaration()
        item['symbol'] = f'p::A{i}'
        declarations.append(item)
    scan.validate_sv_declarations(declarations, [source])
    assert len(texts) == 1
    assert 'package svx_signature_probe_0;' not in texts[0]
    assert texts[0].count('package svx_signature_probe_') == 24
    wrong = deepcopy(declarations)
    wrong[-1]['methods'][0]['return_type']['sv'] = 'string'
    with pytest.raises(bridge.SVXInheritanceError, match=r'p::A23.check return type.*does not match'):
        scan.validate_sv_declarations(wrong, [source])
    wrong[-1]['methods'][0]['return_type']['sv'] = 'int ['
    with pytest.raises(bridge.SVXInheritanceError, match='method signatures of p::A23'):
        scan.validate_sv_declarations(wrong, [source])


def test_record_codec_reuse_is_command_local_without_skipping_member_checks(monkeypatch):
    from test_m8_inheritance import INT
    import svtypes
    metadata = deepcopy(INT)
    metadata.pop('python', None)
    metadata['svtypes'] = svtypes.type_spec_identity(svtypes.Int)
    binding = bridge._type_binding(metadata, 'test', allow_void=False)
    calls = []
    validate = bridge._validate_call_record_members
    materialize = bridge._codec_from_spec

    def checked(*args):
        calls.append(('members', args[2]))
        return validate(*args)

    def codec(spec):
        calls.append(('codec', None))
        return materialize(spec)

    monkeypatch.setattr(bridge, '_validate_call_record_members', checked)
    monkeypatch.setattr(bridge, '_codec_from_spec', codec)
    for _ in range(2):
        with bridge.call_record_generation():
            first = bridge._sv_record_type('sv://perf/A#f', 'request', (('a', binding),))
            second = bridge._sv_record_type('sv://perf/B#f', 'request', (('b', binding),))
            assert first is not second
            assert bridge._call_record_types.get()[('fields', first)] == ('a',)
            assert bridge._call_record_types.get()[('fields', second)] == ('b',)
    assert sum(kind == 'codec' for kind, _ in calls) == 2
    assert sum(kind == 'members' for kind, _ in calls) == 4
