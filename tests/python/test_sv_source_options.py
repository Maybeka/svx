import io
import json
from pathlib import Path

import pytest

from svx.cli import main
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION,
    enrich_virtual_interface_manifest, manifest_from_declarations, manifest_dict,
)
from svx.errors import SVXInheritanceError
from svx.inheritance import parse_manifest
from tests.integration.sv_field_mirror_schema import manifest_data


@pytest.mark.parametrize("enabled", [False, True])
def test_proxy_discovery_obeys_included_conditional_source(tmp_path, enabled):
    pytest.importorskip("pyslang")
    from svx.sv_scan import scan_sv_sources
    from svx.sv_source_options import _source_parse_options

    header = tmp_path / "proxy.svh"
    header.write_text(
        '`ifdef ENABLE_PROXY\n'
        '`SVX_PY_PROXY(BProxy, "py://checks/B", A)\n'
        '`endif\n'
    )
    source = tmp_path / "classes.sv"
    source.write_text(
        'package checks_pkg; class A; endclass\n'
        '`include "proxy.svh"\nendpackage\n'
    )
    options = _source_parse_options(
        {"ENABLE_PROXY": None} if enabled else {}, (), [tmp_path],
        discover_proxies=True,
    )
    facts = scan_sv_sources([source], parse_options=options)
    assert ("checks_pkg::BProxy" in facts) is enabled
    if enabled:
        assert facts["checks_pkg::BProxy"].python_proxy_id == "py://checks/B"
        assert facts["checks_pkg::BProxy"].direct_base == "A"


@pytest.mark.parametrize("predefines,undefines", [({"SVX_PY_PROXY": None}, ()), ({}, ("SVX_PY_PROXY",))])
def test_proxy_discovery_rejects_overridden_marker(predefines, undefines):
    pytest.importorskip("pyslang")
    from svx.sv_source_options import _source_parse_options

    with pytest.raises(SVXInheritanceError, match="reserved during source discovery"):
        _source_parse_options(predefines, undefines, discover_proxies=True)


def declaration_file(tmp_path):
    path = tmp_path / "declarations.json"
    path.write_text(json.dumps({
        "schema_uri": SV_DECLARATION_SCHEMA_URI,
        "schema_version": SV_DECLARATION_SCHEMA_VERSION,
        "classes": [manifest_data()["classes"][0]],
    }))
    return path


def test_manifest_macro_configuration_reaches_member_type_validation(tmp_path):
    declarations = declaration_file(tmp_path)
    source = Path("tests/integration/configured_field_owner.sv")
    kwargs = dict(sv_declaration_files=[declarations], sv_source_files=[source])
    selected = manifest_from_declarations(**kwargs, sv_predefines={"SVX_FIELD_ENABLED": "1"})
    assert selected.classes[0].symbol == "field_owner_pkg::Base"
    with pytest.raises(SVXInheritanceError):
        manifest_from_declarations(**kwargs)
    with pytest.raises(SVXInheritanceError):
        manifest_from_declarations(**kwargs, sv_predefines={"SVX_FIELD_ENABLED": "1"},
                                   sv_undefines=["SVX_FIELD_ENABLED"])
    assert manifest_dict(manifest_from_declarations(
        **kwargs, sv_predefines={"SVX_FIELD_ENABLED": "1"})) == manifest_dict(selected)


@pytest.mark.parametrize('shared', [False, True])
def test_macro_configuration_reaches_handle_and_vif_discovery(tmp_path, shared):
    from tests.integration.constructor_handles_schema import manifest_data as handle_data
    data = handle_data()
    for field in data["classes"][0]["fields"]:
        field.pop("handle")
    paths = []
    for name in ("constructor_handle_types.sv", "external_bus_if.sv"):
        path = tmp_path / name
        path.write_text("`ifdef ENABLE_HANDLES\n" + Path("tests/integration", name).read_text() + "\n`endif\n")
        paths.append(path)
    model = parse_manifest(data)
    settings = {'sv_predefines': {"ENABLE_HANDLES": None}}
    if shared:
        definitions = tmp_path / 'definitions.sv'
        definitions.write_text('`define ENABLE_HANDLES\n')
        paths.insert(0, definitions)
        settings = {'sv_compilation_unit': True}
    enriched = enrich_virtual_interface_manifest(
        model, sv_source_files=paths, **settings)
    fields = enriched.classes[0].fields
    assert fields[0].handle.sv_type == "external_handle_test_pkg::Packet"
    assert fields[1].handle.sv_type == "virtual external_bus_if.master"
    assert fields[1].handle.operations
    assert all(field.handle is None for field in model.classes[0].fields)
    unselected = enrich_virtual_interface_manifest(model, sv_source_files=paths)
    assert all(field.handle is None for field in unselected.classes[0].fields)


def test_cli_macro_configuration_and_check_preserve_outputs(tmp_path):
    target = tmp_path / "manifest.json"
    args = ["inheritance-manifest", "--sv-declarations", str(declaration_file(tmp_path)),
            "--sv-source", "tests/integration/configured_field_owner.sv",
            "--sv-define", "SVX_FIELD_ENABLED=1", "--out", str(target)]
    assert main(args, out=io.StringIO()) == 0
    before = target.read_bytes()
    assert main(args + ["--check"], out=io.StringIO()) == 0
    with pytest.raises(SVXInheritanceError):
        main(args + ["--sv-undefine", "SVX_FIELD_ENABLED", "--check"], out=io.StringIO())
    assert target.read_bytes() == before
    output = tmp_path / "mirrors.sv"
    gen = ["inheritance-gen", "--manifest", str(target), "--sv-source",
           "tests/integration/configured_field_owner.sv", "--sv-define",
           "SVX_FIELD_ENABLED=1", "--sv-out", str(output),
           "--python-out", str(tmp_path / "python"),
           "--artifact-manifest", str(tmp_path / "artifacts.json")]
    assert main(gen, out=io.StringIO()) == 0
    assert main(gen + ["--check"], out=io.StringIO()) == 0


@pytest.mark.parametrize("flags", [
    ["--sv-define", "ENABLE"], ["--sv-undefine", "ENABLE"],
    ["--sv-define", "ENABLE=1", "--sv-define", "ENABLE=2"],
    ["--sv-compilation-unit"],
    ["--sv-include-dir", "includes"],
])
def test_cli_rejects_invalid_config_before_importing_user_modules(tmp_path, flags):
    with pytest.raises(SystemExit):
        main(["inheritance-manifest", "--python-module", "must_not_be_imported",
              "--out", str(tmp_path / "manifest.json"), *flags], out=io.StringIO())


@pytest.mark.parametrize("command", ["inheritance-manifest", "inheritance-gen"])
def test_cli_rejects_invalid_macro_names(tmp_path, command):
    args = (["--out", str(tmp_path / "manifest.json")] if command == "inheritance-manifest"
            else ["--manifest", str(tmp_path / "missing.json")])
    with pytest.raises(SVXInheritanceError, match="identifier names"):
        main([command, *args, "--sv-source", "missing.sv", "--sv-define", "BAD-NAME"],
             out=io.StringIO())


def test_generation_inputs_detect_unchanged_output_after_include_or_macro_change(tmp_path):
    source = tmp_path / "source.sv"
    included = tmp_path / "owner.svh"
    included.write_text(Path("tests/integration/sv_field_owner.sv").read_text())
    source.write_text('`include "owner.svh"\n')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(manifest_data()))
    artifacts = tmp_path / "artifacts.json"
    output = tmp_path / "mirrors.sv"
    args = ["inheritance-gen", "--manifest", str(manifest), "--sv-source", str(source),
            "--sv-define", "UNUSED=1", "--python-out", str(tmp_path / "python"),
            "--sv-out", str(output), "--artifact-manifest", str(artifacts)]
    assert main(args, out=io.StringIO()) == 0
    before_output = output.read_bytes()
    before_artifacts = artifacts.read_bytes()
    inputs = json.loads(before_artifacts)["generation_inputs"]
    assert inputs["sv_sources"] == ["source.sv"]
    assert {entry["path"] for entry in inputs["sv_dependencies"]} == {"source.sv", "owner.svh"}
    assert inputs["sv_predefines"] == {"UNUSED": "1"}
    with pytest.raises(SystemExit, match="artifacts are stale"):
        main(args + ["--sv-compilation-unit", "--check"], out=io.StringIO())
    assert artifacts.read_bytes() == before_artifacts
    included.write_text(included.read_text() + "// implementation review\n")
    with pytest.raises(SystemExit, match="artifacts are stale"):
        main(args + ["--check"], out=io.StringIO())
    assert artifacts.read_bytes() == before_artifacts
    assert output.read_bytes() == before_output
    assert main(args, out=io.StringIO()) == 0
    assert output.read_bytes() == before_output
    assert main(args + ["--check"], out=io.StringIO()) == 0
    changed = ["UNUSED=2" if value == "UNUSED=1" else value for value in args]
    with pytest.raises(SystemExit, match="artifacts are stale"):
        main(changed + ["--check"], out=io.StringIO())
    assert main(changed, out=io.StringIO()) == 0
    assert output.read_bytes() == before_output
    # Raw input changes matter even when the normalized manifest is identical.
    manifest.write_text(json.dumps(manifest_data(), indent=2))
    with pytest.raises(SystemExit, match="artifacts are stale"):
        main(changed + ["--check"], out=io.StringIO())


@pytest.mark.parametrize("collision", ["direct", "include", "hardlink", "obsolete", "search"])
def test_generation_never_overwrites_or_prunes_source_inputs(tmp_path, collision):
    from svx.inheritance import write_generated_sources
    python = tmp_path / "python"
    owner = "// Generated by svx inheritance-gen. Do not edit.\n" + Path(
        "tests/integration/sv_field_owner.sv").read_text()
    if collision == "obsolete":
        write_generated_sources({Path("owner.sv"): owner}, python, ".svx-generated-python.json")
        included = python / "owner.sv"
    else:
        included = tmp_path / "owner.sv"
        if collision == 'search':
            included = tmp_path / 'external' / 'owner.sv'
            included.parent.mkdir()
        included.write_text(owner)
    source = tmp_path / "source.sv"
    source.write_text('`include "' + included.relative_to(tmp_path).as_posix() + '"\n')
    if collision == 'search':
        source.write_text('`include "owner.sv"\n')
    if collision == "direct":
        source = included
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(manifest_data()))
    output = tmp_path / "mirrors.sv"
    if collision in {"direct", "include", "search"}:
        output = included
    elif collision == "hardlink":
        output.hardlink_to(included)
    args = ["inheritance-gen", "--manifest", str(manifest), "--sv-source", str(source),
            "--python-out", str(python), "--sv-out", str(output)]
    if collision == 'search':
        args.extend(['--sv-include-dir', str(included.parent)])
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(SVXInheritanceError, match="input source"):
        main(args, out=io.StringIO())
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns)
             for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


def test_manifest_discovery_never_replaces_declaration_input(tmp_path):
    source = declaration_file(tmp_path)
    before = source.read_bytes(), source.stat().st_mtime_ns
    with pytest.raises(SVXInheritanceError, match="input source"):
        main(["inheritance-manifest", "--sv-declarations", str(source), "--out", str(source)],
             out=io.StringIO())
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before


def test_shared_compilation_unit_keeps_macro_order_in_all_validation_passes(tmp_path):
    definitions = tmp_path / 'definitions.sv'
    definitions.write_text('`define SVX_FIELD_ENABLED 1\n')
    source = Path('tests/integration/configured_field_owner.sv')
    declarations = declaration_file(tmp_path)
    kwargs = dict(sv_declaration_files=[declarations])
    selected = manifest_from_declarations(**kwargs, sv_source_files=[definitions, source],
                                          sv_compilation_unit=True)
    assert selected.classes[0].symbol == 'field_owner_pkg::Base'
    for paths, shared in (([definitions, source], False), ([source, definitions], True)):
        with pytest.raises(SVXInheritanceError):
            manifest_from_declarations(**kwargs, sv_source_files=paths, sv_compilation_unit=shared)
    target = tmp_path / 'manifest.json'
    args = ['inheritance-manifest', '--sv-declarations', str(declarations),
            '--sv-source', str(definitions), '--sv-source', str(source),
            '--sv-compilation-unit', '--out', str(target)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    artifacts = tmp_path / 'artifacts.json'
    generation = ['inheritance-gen', '--manifest', str(target),
                  '--sv-source', str(definitions), '--sv-source', str(source),
                  '--sv-compilation-unit', '--python-out', str(tmp_path / 'python'),
                  '--sv-out', str(tmp_path / 'mirrors.sv'), '--artifact-manifest', str(artifacts)]
    assert main(generation, out=io.StringIO()) == 0
    assert main(generation + ['--check'], out=io.StringIO()) == 0
    inputs = json.loads(artifacts.read_text())['generation_inputs']
    assert inputs['source_mode'] == 'shared-compilation-unit'
    assert inputs['sv_sources'][0] == 'definitions.sv'
    assert any(entry['path'].endswith('sv_field_owner.sv') for entry in inputs['sv_dependencies'])


def test_shared_compilation_unit_parse_errors_keep_original_location(tmp_path):
    from svx.sv_scan import scan_sv_sources
    definitions = tmp_path / 'definitions.sv'
    definitions.write_text('`define ENABLED\n')
    broken = tmp_path / 'broken.sv'
    broken.write_text('`ifdef ENABLED\npackage broken;\nclass ;\nendpackage\n`endif\n')
    with pytest.raises(SVXInheritanceError, match=r'broken.sv:3:'):
        scan_sv_sources([definitions, broken], compilation_unit=True)


def test_include_search_order_matches_semantic_validation_and_input_records(tmp_path):
    source = Path('tests/integration/include_search_owner.sv')
    good = Path('tests/integration/include_good')
    bad = Path('tests/integration/include_bad')
    kwargs = dict(sv_declaration_files=[declaration_file(tmp_path)], sv_source_files=[source])
    assert manifest_from_declarations(**kwargs, sv_include_dirs=iter([good, bad])).classes
    for directories in ([], [bad, good]):
        with pytest.raises(SVXInheritanceError):
            manifest_from_declarations(**kwargs, sv_include_dirs=directories)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(manifest_data()))
    artifacts = tmp_path / 'artifacts.json'
    args = ['inheritance-gen', '--manifest', str(manifest), '--sv-source', str(source),
            '--sv-include-dir', str(good), '--sv-include-dir', str(bad),
            '--python-out', str(tmp_path / 'python'), '--sv-out', str(tmp_path / 'mirrors.sv'),
            '--artifact-manifest', str(artifacts)]
    assert main(args, out=io.StringIO()) == 0
    assert main(args + ['--check'], out=io.StringIO()) == 0
    inputs = json.loads(artifacts.read_text())['generation_inputs']
    assert inputs['sv_include_dirs'][0].endswith('include_good')
    assert inputs['sv_include_dirs'][1].endswith('include_bad')
    dependencies = [entry['path'] for entry in inputs['sv_dependencies']]
    assert any(path.endswith('include_good/field_binding.svh') for path in dependencies)
    assert not any(path.endswith('include_bad/field_binding.svh') for path in dependencies)
    changed = [str(bad) if value == str(good) else str(good) if value == str(bad) else value for value in args]
    with pytest.raises(SystemExit, match='artifacts are stale'):
        main(changed + ['--check'], out=io.StringIO())


@pytest.mark.parametrize('directories', ['includes', [b'includes'], [7], [''], ['bad\npath']])
def test_include_search_rejects_invalid_path_inputs(directories):
    from svx.sv_source_options import _source_parse_options
    with pytest.raises((TypeError, SVXInheritanceError)):
        _source_parse_options(None, (), directories)


def test_empty_include_iterator_does_not_require_source_inputs(tmp_path):
    kwargs = dict(sv_declaration_files=[declaration_file(tmp_path)])
    assert manifest_dict(manifest_from_declarations(**kwargs, sv_include_dirs=iter(()))) == manifest_dict(
        manifest_from_declarations(**kwargs))
def test_missing_source_frontend_has_actionable_dependency_error(monkeypatch):
    import sys
    import pytest
    from svx.errors import SVXInheritanceError
    from svx.sv_source_options import _source_parse_options

    monkeypatch.setitem(sys.modules, 'pyslang', None)
    with pytest.raises(SVXInheritanceError, match="optional 'pyslang'.*manifest.*extra"):
        _source_parse_options(None, ())
