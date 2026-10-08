import io
import builtins
import importlib
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from svx.cli import main
from svx.declarations import manifest_dict
from svx.errors import SVXInheritanceError
from svx.inheritance import load_manifest, parse_manifest
from tests.integration.sv_field_mirror_schema import manifest_data
from tests.integration.discovery_provenance_contract import setup_record


def generation_args(root, manifest):
    return ['inheritance-gen', '--manifest', str(manifest),
            '--python-out', str(root / 'generated' / 'python'),
            '--sv-out', str(root / 'generated' / 'mirrors.sv'),
            '--artifact-manifest', str(root / 'generated' / 'artifacts.json')]


def test_generation_fingerprints_reuse_only_current_validated_bytes(tmp_path, monkeypatch):
    import svx.cli

    manifest, source, evidence, _, _ = setup_record(tmp_path)
    args = svx.cli.build_parser().parse_args(generation_args(tmp_path, manifest))
    reads = {source.resolve(): 0, evidence.resolve(): 0}
    read = Path.read_bytes

    def counted(path):
        resolved = path.resolve()
        if resolved in reads:
            reads[resolved] += 1
        return read(path)

    monkeypatch.setattr(Path, 'read_bytes', counted)
    inputs = svx.cli._generation_inputs(args, tmp_path)
    assert reads == {source.resolve(): 1, evidence.resolve(): 1}
    records = inputs['discovery_inputs']
    assert {item['sha256'] for item in records} == {
        hashlib.sha256(read(source)).hexdigest(), hashlib.sha256(read(evidence)).hexdigest()}
    source.write_text('Scalar = 16\n')
    with pytest.raises(SVXInheritanceError, match='discovery source changed'):
        svx.cli._generation_inputs(args, tmp_path)
    assert reads == {source.resolve(): 2, evidence.resolve(): 2}


def snapshot(root):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
            for path in root.rglob('*') if path.is_file()}


def test_provenance_load_roundtrip_relocation_and_legacy(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    manifest, source, evidence, data, record = setup_record(original)
    loaded = load_manifest(manifest)
    normalized = manifest_dict(loaded)
    assert normalized['discovery_provenance'] == data['discovery_provenance']
    assert len(loaded.classes) == len(data['classes'])
    assert manifest_dict(parse_manifest(manifest_data())) == manifest_dict(
        parse_manifest({key: value for key, value in normalized.items() if key != 'discovery_provenance'}))
    moved = tmp_path / 'moved'
    shutil.copytree(original, moved)
    assert load_manifest(moved / manifest.name) == loaded
    args = generation_args(moved, moved / manifest.name)
    assert main(args, out=io.StringIO()) == 0
    before = snapshot(moved)
    assert main(args + ['--check'], out=io.StringIO()) == 0
    assert main(args, out=io.StringIO()) == 0
    assert snapshot(moved) == before
    inputs = json.loads((moved / 'generated' / 'artifacts.json').read_text())['generation_inputs']
    assert {item['path'] for item in inputs['discovery_inputs']} == {
        '../discovery.json', '../declaration_types.py'}


@pytest.mark.parametrize('damage', [
    'source_edit', 'missing_source', 'missing_record', 'contract_edit',
    'bad_digest', 'duplicate_source', 'absolute_source', 'alias_source', 'null_marker',
])
def test_invalid_discovery_evidence_rejects_before_class_parsing_and_preserves_outputs(
        tmp_path, monkeypatch, damage):
    manifest, source, evidence, data, record = setup_record(tmp_path)
    args = generation_args(tmp_path, manifest)
    assert main(args, out=io.StringIO()) == 0
    if damage == 'source_edit':
        source.write_text('Scalar = 16\n')
    elif damage == 'missing_source':
        source.unlink()
    elif damage == 'missing_record':
        evidence.unlink()
    elif damage == 'contract_edit':
        data['classes'][0]['canonical_id'] += 'Changed'
        manifest.write_text(json.dumps(data))
    elif damage == 'null_marker':
        data['discovery_provenance'] = None
        manifest.write_text(json.dumps(data))
    else:
        if damage == 'bad_digest':
            record['sources'][0]['sha256'] = 'not-a-digest'
        elif damage == 'duplicate_source':
            record['sources'].append(dict(record['sources'][0]))
        elif damage == 'absolute_source':
            record['sources'][0]['path'] = str(source)
        elif damage == 'alias_source':
            (tmp_path / 'alias.py').symlink_to(source)
            record['sources'].append({**record['sources'][0], 'path': 'alias.py'})
        evidence.write_text(json.dumps(record))
    before = snapshot(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError('stale discovery evidence must reject before class/factory parsing')

    monkeypatch.setattr('svx.inheritance._parse_class', forbidden)
    with pytest.raises(SVXInheritanceError, match='discovery'):
        load_manifest(manifest)
    for flags in ([], ['--check']):
        with pytest.raises(SVXInheritanceError, match='discovery'):
            main(args + flags, out=io.StringIO())
        assert snapshot(tmp_path) == before


def test_provenance_requires_file_context(tmp_path):
    _, _, _, data, _ = setup_record(tmp_path)
    with pytest.raises(SVXInheritanceError, match='file context'):
        parse_manifest(data)


@pytest.mark.parametrize('output', ['source', 'record'])
def test_discovery_inputs_cannot_be_overwritten(tmp_path, output):
    manifest, source, evidence, _, _ = setup_record(tmp_path)
    args = generation_args(tmp_path, manifest)
    args[args.index('--sv-out') + 1] = str(source if output == 'source' else evidence)
    before = snapshot(tmp_path)
    with pytest.raises(SVXInheritanceError, match='input source|non-generated file'):
        main(args, out=io.StringIO())
    assert snapshot(tmp_path) == before


def test_discovery_source_edit_during_generation_preserves_outputs(tmp_path, monkeypatch):
    manifest, source, _, _, _ = setup_record(tmp_path)
    args = generation_args(tmp_path, manifest)
    assert main(args, out=io.StringIO()) == 0
    before = snapshot(tmp_path / 'generated')
    import svx.cli
    render = svx.cli.emit_sv_mirrors

    def change_source(*args, **kwargs):
        result = render(*args, **kwargs)
        source.write_text('Scalar = 16\n')
        return result

    monkeypatch.setattr(svx.cli, 'emit_sv_mirrors', change_source)
    with pytest.raises(SVXInheritanceError, match='generation inputs could not be revalidated'):
        main(args, out=io.StringIO())
    assert snapshot(tmp_path / 'generated') == before


def test_cached_discovery_requires_current_prior_evidence(tmp_path, monkeypatch):
    from tests.python.test_iterative_discovery_workflow import source_text

    name = 'audited_discovery_entry'
    source = tmp_path / (name + '.py')
    source.write_text(source_text())
    target = tmp_path / 'manifest.json'
    args = ['inheritance-manifest', '--python-module', name, '--out', str(target)]
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        assert main(args, out=io.StringIO()) == 0
        before = snapshot(tmp_path)
        assert main(args + ['--check'], out=io.StringIO()) == 0
        assert main(args, out=io.StringIO()) == 0
        assert snapshot(tmp_path) == before
        source.write_text(source_text(parameter=True))
        changed = snapshot(tmp_path)
        for flags in ([], ['--check']):
            with pytest.raises(SVXInheritanceError, match='cached without current discovery evidence'):
                main(args + flags, out=io.StringIO())
            assert snapshot(tmp_path) == changed
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize('statement', [
    'import cached_types; Scalar = cached_types.Scalar',
    'from cached_types import Scalar',
    'import importlib; Scalar = importlib.import_module("cached_types").Scalar',
])
@pytest.mark.parametrize('changed', [False, True])
def test_unaudited_cached_helper_cannot_certify_new_entry(tmp_path, monkeypatch, statement, changed):
    from tests.python.test_iterative_discovery_workflow import source_text

    monkeypatch.syspath_prepend(str(tmp_path))
    helper = tmp_path / 'cached_types.py'
    helper.write_text('import svtypes\nScalar = svtypes.Bit[8]\n')
    (tmp_path / 'cached_owner.py').write_text(
        source_text().replace('import svtypes\n', 'import svtypes\n' + statement + '\n')
        .replace('def calculate(self)', 'def calculate(self, value: Scalar)'))
    target = tmp_path / 'generated' / 'manifest.json'
    args = ['inheritance-manifest', '--python-module', 'cached_owner', '--out', str(target)]
    original_import, original_import_module = builtins.__import__, importlib.import_module
    try:
        importlib.import_module('cached_types')
        if changed:
            helper.write_text('import svtypes\nScalar = svtypes.Bit[16]\n')
        for flags in ([], ['--check']):
            with pytest.raises(SVXInheritanceError, match='dependency is cached without current discovery evidence'):
                main(args + flags, out=io.StringIO())
            assert not target.exists() and not target.parent.exists()
            assert builtins.__import__ is original_import
            assert importlib.import_module is original_import_module
    finally:
        for name in ('cached_types', 'cached_owner'):
            sys.modules.pop(name, None)


@pytest.mark.parametrize('statement', [
    'import lazy_cached_types; return lazy_cached_types.Codec()',
    'from lazy_cached_types import Codec; return Codec()',
    'import importlib; return importlib.import_module("lazy_cached_types").Codec()',
])
@pytest.mark.parametrize('changed', [False, True])
def test_lazy_codec_materialization_rejects_unaudited_cached_helper(tmp_path, monkeypatch, statement, changed):
    from tests.integration.sv_field_mirror_schema import manifest_data
    from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION

    monkeypatch.syspath_prepend(str(tmp_path))
    helper = tmp_path / 'lazy_cached_types.py'
    helper.write_text('from svtypes import Int\nCodec = Int\n')
    (tmp_path / 'lazy_codec_factory.py').write_text('def make():\n    ' + statement + '\n')
    data = manifest_data()['classes'][0]
    binding = data['fields'][0]['type']
    binding.pop('svtypes')
    binding['python'] = {'module': 'lazy_codec_factory', 'symbol': 'make'}
    declarations = tmp_path / 'declarations.json'
    declarations.write_text(json.dumps({
        'schema_uri': SV_DECLARATION_SCHEMA_URI,
        'schema_version': SV_DECLARATION_SCHEMA_VERSION, 'classes': [data],
    }))
    target = tmp_path / 'generated' / 'manifest.json'
    args = ['inheritance-manifest', '--sv-declarations', str(declarations), '--out', str(target)]
    original_import, original_import_module = builtins.__import__, importlib.import_module
    try:
        importlib.import_module('lazy_cached_types')
        if changed:
            helper.write_text('from svtypes import Bit\nCodec = Bit[16]\n')
        with pytest.raises(SVXInheritanceError, match='dependency is cached without current discovery evidence'):
            main(args, out=io.StringIO())
        assert not target.exists() and not target.parent.exists()
        assert builtins.__import__ is original_import
        assert importlib.import_module is original_import_module
        for name in ('lazy_cached_types', 'lazy_codec_factory'):
            sys.modules.pop(name, None)
        helper.write_text('from svtypes import Int\nCodec = Int\n')
        assert main(args, out=io.StringIO()) == 0
        from svx.discovery_provenance import validate_discovery_provenance
        assert helper.resolve() in validate_discovery_provenance(json.loads(target.read_text()), target)
        before = snapshot(target.parent)
        assert main(args + ['--check'], out=io.StringIO()) == 0
        assert main(args, out=io.StringIO()) == 0
        assert snapshot(target.parent) == before
    finally:
        for name in ('lazy_cached_types', 'lazy_codec_factory'):
            sys.modules.pop(name, None)


def test_audited_cached_helper_is_reused_without_output_rewrites(tmp_path, monkeypatch):
    from tests.python.test_iterative_discovery_workflow import source_text

    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / 'cached_types.py').write_text('import svtypes\nScalar = svtypes.Bit[8]\n')
    (tmp_path / 'cached_owner.py').write_text(
        source_text().replace('import svtypes\n', 'import svtypes\nfrom cached_types import Scalar\n')
        .replace('def calculate(self)', 'def calculate(self, value: Scalar)'))
    target = tmp_path / 'generated' / 'manifest.json'
    args = ['inheritance-manifest', '--python-module', 'cached_owner', '--out', str(target)]
    try:
        assert main(args, out=io.StringIO()) == 0
        before = snapshot(target.parent)
        sys.modules.pop('cached_owner')
        for flags in ([], ['--check']):
            assert main(args + flags, out=io.StringIO()) == 0
            assert snapshot(target.parent) == before
    finally:
        for name in ('cached_types', 'cached_owner'):
            sys.modules.pop(name, None)


def test_unaudited_cached_relative_package_helper_is_rejected(tmp_path, monkeypatch):
    from tests.python.test_iterative_discovery_workflow import source_text

    monkeypatch.syspath_prepend(str(tmp_path))
    package = tmp_path / 'cached_pkg'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'types.py').write_text('import svtypes\nScalar = svtypes.Bit[8]\n')
    (package / 'owner.py').write_text(
        source_text().replace('import svtypes\n', 'import svtypes\nfrom .types import Scalar\n')
        .replace('def calculate(self)', 'def calculate(self, value: Scalar)'))
    target = tmp_path / 'generated' / 'manifest.json'
    try:
        importlib.import_module('cached_pkg.types')
        with pytest.raises(SVXInheritanceError, match='dependency is cached without current discovery evidence'):
            main(['inheritance-manifest', '--python-module', 'cached_pkg.owner',
                  '--out', str(target)], out=io.StringIO())
        assert not target.parent.exists()
    finally:
        for name in ('cached_pkg', 'cached_pkg.types', 'cached_pkg.owner'):
            sys.modules.pop(name, None)


@pytest.mark.parametrize('configuration', [
    {'unknown': []}, {'sv_sources': ['/absolute/source.sv']},
    {'source_mode': 'unsupported'}, {'python_modules': 'not-a-list'},
    {'source_mode': []}, {'source_mode': {}},
])
def test_invalid_discovery_configuration_is_rejected(tmp_path, configuration):
    manifest, _, evidence, _, record = setup_record(tmp_path)
    record['configuration'] = configuration
    evidence.write_text(json.dumps(record))
    with pytest.raises(SVXInheritanceError, match='invalid discovery provenance'):
        load_manifest(manifest)


def test_api_load_revalidates_sources_after_class_materialization(tmp_path, monkeypatch):
    import svx.inheritance

    manifest, source, _, _, _ = setup_record(tmp_path)
    parse_class = svx.inheritance._parse_class

    def changing_factory(*args, **kwargs):
        result = parse_class(*args, **kwargs)
        source.write_text('Scalar = 16\n')
        return result

    monkeypatch.setattr(svx.inheritance, '_parse_class', changing_factory)
    with pytest.raises(SVXInheritanceError, match='discovery source changed'):
        load_manifest(manifest)


@pytest.mark.parametrize('changed_text', [False, True])
@pytest.mark.parametrize('shared', [False, True])
def test_new_preferred_header_invalidates_discovery_before_generation(tmp_path, monkeypatch, changed_text, shared):
    from tests.python.test_iterative_discovery_workflow import run_cli
    from tests.integration.discovery_selection import selection_inputs

    discovery, args, first, text = selection_inputs(tmp_path, shared)
    result = run_cli(tmp_path, *discovery)
    assert result.returncode == 0, result.stderr
    assert main(args, out=io.StringIO()) == 0
    original = snapshot(tmp_path / 'generated')
    (first / 'owner.svh').write_text(text + ('// new candidate\n' if changed_text else ''))

    def forbidden(*args, **kwargs):
        raise AssertionError('changed dependency selection reached class parsing')

    with monkeypatch.context() as context:
        context.setattr('svx.inheritance._parse_class', forbidden)
        for flags in ([], ['--check']):
            with pytest.raises(SVXInheritanceError, match='discovery dependency selection changed'):
                main(args + flags, out=io.StringIO())
            assert snapshot(tmp_path / 'generated') == original
    result = run_cli(tmp_path, *discovery)
    assert result.returncode == 0, result.stderr
    assert main(args, out=io.StringIO()) == 0
    revised = snapshot(tmp_path / 'generated')
    assert {path: value for path, value in revised.items() if path.name != 'artifacts.json'} == {
        path: value for path, value in original.items() if path.name != 'artifacts.json'}
    assert main(args + ['--check'], out=io.StringIO()) == 0


def test_discovery_second_publish_failure_restores_both_outputs(tmp_path, monkeypatch):
    from tests.python.test_sv_source_options import declaration_file

    declarations = declaration_file(tmp_path)
    target = tmp_path / 'manifest.json'
    args = ['inheritance-manifest', '--sv-declarations', str(declarations), '--out', str(target)]
    assert main(args, out=io.StringIO()) == 0
    data = json.loads(declarations.read_text())
    data['classes'][0]['canonical_id'] += 'Changed'
    data['classes'][0]['symbol'] += 'Changed'
    for method in data['classes'][0]['methods']:
        method['canonical_id'] = data['classes'][0]['canonical_id'] + '#' + method['name']
    declarations.write_text(json.dumps(data))
    before = snapshot(tmp_path)
    replace_file = Path.replace

    def fail_manifest(source, destination):
        if source.name.endswith('.tmp') and Path(destination) == target:
            raise OSError('injected second publication failure')
        return replace_file(source, destination)

    with monkeypatch.context() as context:
        context.setattr(Path, 'replace', fail_manifest)
        with pytest.raises(OSError, match='second publication failure'):
            main(args, out=io.StringIO())
        assert snapshot(tmp_path) == before
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0


@pytest.mark.parametrize('out', ['/', '.'])
def test_discovery_output_requires_filename(tmp_path, out):
    from tests.python.test_sv_source_options import declaration_file

    declarations = declaration_file(tmp_path)
    before = snapshot(tmp_path)
    with pytest.raises(SVXInheritanceError, match='requires a filename'):
        main(['inheritance-manifest', '--sv-declarations', str(declarations), '--out', out],
             out=io.StringIO())
    assert snapshot(tmp_path) == before
