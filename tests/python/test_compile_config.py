import io
import json
from pathlib import Path

import pytest

from svx.cli import main
from svx.compile_config import import_compile_configuration, replay_build_record
from svx.errors import SVXInheritanceError


@pytest.mark.parametrize('flag', ['-top', '--top-module', '-top=', '--top-module='])
def test_import_preserves_original_top_selection(tmp_path, flag):
    source = tmp_path / 'design.sv'
    source.write_text('module selected;endmodule module unused;endmodule')
    argument = flag + 'selected' if flag.endswith('=') else flag + ' selected'
    filelist = tmp_path / 'project.f'
    filelist.write_text('design.sv ' + argument + '\n')
    config = import_compile_configuration(dict(directory=str(tmp_path), filelists=['project.f']))
    assert config.top_modules == ['selected']
    assert config.as_dict(tmp_path)['top_modules'] == ['selected']
    assert not config.ignored


def test_nested_filelists_macros_paths_and_order(tmp_path, monkeypatch):
    (tmp_path / 'lists').mkdir()
    for name in ('base.sv', 'child.sv'):
        (tmp_path / name).write_text('')
    (tmp_path / 'lists/nested.f').write_text('../child.sv\n')
    (tmp_path / 'root.f').write_text(
        '// files\n+incdir+$PROJECT/inc+"$PROJECT/path with spaces"\n'
        '+define+WIDTH=8+ENABLED -UENABLED -DWIDTH=16\n'
        'base.sv /* dependencies */ -F lists/nested.f\n')
    monkeypatch.setenv('PROJECT', str(tmp_path))
    config = import_compile_configuration(dict(directory=str(tmp_path), filelists=['root.f']), tmp_path)
    assert config.sources == [tmp_path / 'base.sv', tmp_path / 'child.sv']
    assert config.include_dirs == [tmp_path / 'inc', tmp_path / 'path with spaces']
    assert config.defines == {'WIDTH': '16'}
    assert config.undefines == ['ENABLED']
    assert config.inputs == [tmp_path / 'root.f', tmp_path / 'lists/nested.f']


def test_command_uses_its_recorded_working_directory(tmp_path):
    source = tmp_path / 'top.sv'
    source.write_text('')
    (tmp_path / 'input.f').write_text('top.sv')
    command = tmp_path / 'command.json'
    command.write_text(json.dumps(dict(directory='.', arguments=[
        'compiler', '-f', 'input.f', '-DNAME="literal"', '-I', 'inc', '-o', 'binary', '--single-unit'])))
    config = import_compile_configuration(dict(commands=[str(command)]))
    assert config.sources == [source]
    assert config.defines['NAME'] == '"literal"'
    assert config.shared
    assert config.ignored == [['-o', 'binary']]


@pytest.mark.parametrize('flag', ['-unknown', '-xlrm unsupported'])
def test_semantic_options_not_silently_discarded(tmp_path, flag):
    filelist = tmp_path / 'bad.f'
    filelist.write_text(flag)
    with pytest.raises(SVXInheritanceError, match='unsupported'):
        import_compile_configuration(dict(filelists=[str(filelist)]))


def test_filelist_cycle_rejected(tmp_path):
    path = tmp_path / 'cycle.f'
    path.write_text('-f cycle.f')
    with pytest.raises(SVXInheritanceError, match='recursive filelist'):
        import_compile_configuration(dict(directory=str(tmp_path), filelists=[str(path)]))


def test_undefined_environment_variable_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv('SVX_MISSING_INPUT', raising=False)
    path = tmp_path / 'env.f'
    path.write_text('$SVX_MISSING_INPUT/top.sv')
    with pytest.raises(SVXInheritanceError, match='undefined build environment'):
        import_compile_configuration(dict(filelists=[str(path)]))


def test_same_filelist_is_replayed_against_current_environment(tmp_path, monkeypatch):
    for name in ('one', 'two'):
        (tmp_path / name).mkdir()
        (tmp_path / name / 'top.sv').write_text('')
    filelist = tmp_path / 'env.f'
    filelist.write_text('$SVX_INPUT/top.sv')
    monkeypatch.setenv('SVX_INPUT', str(tmp_path / 'one'))
    recipe = dict(filelists=['env.f'])
    record = dict(recipe=recipe, configuration=import_compile_configuration(recipe, tmp_path).as_dict(tmp_path))
    replay_build_record(record, tmp_path)
    monkeypatch.setenv('SVX_INPUT', str(tmp_path / 'two'))
    with pytest.raises(SVXInheritanceError, match='build configuration changed'):
        replay_build_record(record, tmp_path)


def test_inspection_cli_and_explicit_overrides(tmp_path):
    (tmp_path / 'a.sv').write_text('')
    (tmp_path / 'list.f').write_text('+define+WIDTH=8\na.sv')
    out = io.StringIO()
    main(['compile-config', '--sv-filelist', str(tmp_path / 'list.f'),
          '--sv-build-directory', str(tmp_path), '--sv-define', 'WIDTH=16'], out=out)
    assert json.loads(out.getvalue())['defines'] == {'WIDTH': '16'}


def test_original_implicit_library_is_imported(tmp_path, monkeypatch):
    directory = tmp_path / 'tool/etc/uvm-1.2'
    directory.mkdir(parents=True)
    (directory / 'uvm_pkg.sv').write_text('package uvm_pkg; endpackage')
    monkeypatch.setattr('svx.compile_config._implicit_uvm_library', lambda library: directory)
    filelist = tmp_path / 'library.f'
    filelist.write_text('-ntb_opts uvm-1.2')
    config = import_compile_configuration(dict(filelists=[str(filelist)]))
    assert config.sources == [directory / 'uvm_pkg.sv']
    assert config.include_dirs == [directory]


def test_generation_check_reimports_filelists(tmp_path):
    from tests.integration.sv_field_mirror_schema import manifest_data
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(manifest_data()))
    (tmp_path / 'types.sv').write_text(Path('tests/integration/configured_field_owner.sv').read_text())
    (tmp_path / 'sv_field_owner.sv').write_text(Path('tests/integration/sv_field_owner.sv').read_text())
    filelist = tmp_path / 'files.f'
    filelist.write_text('+define+SVX_FIELD_ENABLED=1\ntypes.sv\n')
    args = ['inheritance-gen', '--manifest', str(manifest), '--sv-filelist', str(filelist),
            '--sv-build-directory', str(tmp_path), '--python-out', str(tmp_path / 'python'),
            '--sv-out', str(tmp_path / 'bridge.sv'), '--artifact-manifest', str(tmp_path / 'artifacts.json')]
    main(args, out=io.StringIO())
    main([*args, '--check'], out=io.StringIO())
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (tmp_path / 'python').rglob('*.py')}
    filelist.write_text('+define+SVX_FIELD_ENABLED=1\n+define+EXTRA=1\ntypes.sv\n')
    with pytest.raises(SystemExit, match='stale'):
        main([*args, '--check'], out=io.StringIO())
    assert all((p.read_bytes(), p.stat().st_mtime_ns) == value for p, value in before.items())


def test_discovery_provenance_replays_original_build_input(tmp_path):
    from tests.integration.sv_field_mirror_schema import manifest_data
    from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION
    from svx.inheritance import load_manifest
    declaration = tmp_path / 'declarations.json'
    declaration.write_text(json.dumps(dict(schema_uri=SV_DECLARATION_SCHEMA_URI,
                                         schema_version=SV_DECLARATION_SCHEMA_VERSION,
                                         classes=[manifest_data()['classes'][0]])))
    source = tmp_path / 'types.sv'
    source.write_text(Path('tests/integration/sv_field_owner.sv').read_text())
    filelist = tmp_path / 'files.f'
    filelist.write_text('types.sv')
    target = tmp_path / 'discovered.json'
    args = ['inheritance-manifest', '--sv-declarations', str(declaration), '--sv-filelist',
            str(filelist), '--sv-build-directory', str(tmp_path), '--out', str(target)]
    main(args, out=io.StringIO())
    load_manifest(target)
    main([*args, '--check'], out=io.StringIO())
    filelist.write_text('types.sv\n// original build changed\n')
    with pytest.raises(SVXInheritanceError, match='discovery source changed'):
        load_manifest(target)


def test_legacy_protected_payload_is_opaque_not_a_class_definition(tmp_path):
    from svx.sv_scan import scan_sv_sources
    from svx.sv_source_options import _source_parse_options
    source = tmp_path / 'protected.sv'
    source.write_text('`protected\nopaque payload ?! not SV\n`endprotected\n'
                      'package visible; class A; endclass endpackage\n')
    facts = scan_sv_sources([source], parse_options=_source_parse_options({}, []))
    assert set(facts) == {'visible::A'}


def test_inspection_cannot_overwrite_filelist(tmp_path):
    filelist = tmp_path / 'empty.f'
    filelist.write_text('// preserve this\n')
    with pytest.raises(SVXInheritanceError, match='input'):
        main(['compile-config', '--sv-filelist', str(filelist), '--out', str(filelist)])
    assert filelist.read_text() == '// preserve this\n'


def test_scanner_handles_comma_separated_properties_in_dependencies(tmp_path):
    from svx.sv_scan import scan_sv_sources
    source = tmp_path / 'multi.sv'
    source.write_text('package p; class A; int first, second; endclass endpackage')
    facts = scan_sv_sources([source])
    assert [field.name for field in facts['p::A'].fields] == ['first', 'second']
