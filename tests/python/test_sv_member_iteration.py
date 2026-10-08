from io import StringIO
import json

import pytest

from svtypes import Int
from svx.cli import main
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION, inheritance_parameter,
)
from svx.errors import SVXInheritanceError


@pytest.mark.parametrize("changed", ["constructor", "field"])
def test_member_type_edit_preserves_last_valid_manifest(tmp_path, changed):
    pytest.importorskip("pyslang")
    source = tmp_path / "source.sv"
    sidecar = tmp_path / "declarations.json"
    output = tmp_path / "manifest.json"
    text = ("package p; class A; int count; function new(input int seed); "
            "count=seed; endfunction endclass endpackage\n")
    source.write_text(text)
    integer = inheritance_parameter("seed", Int)
    sidecar.write_text(json.dumps({
        "schema_uri": SV_DECLARATION_SCHEMA_URI,
        "schema_version": SV_DECLARATION_SCHEMA_VERSION,
        "classes": [{"canonical_id": "sv://p/A", "language": "sv", "symbol": "p::A",
                     "constructor": {"initiator": "python", "parameters": [integer]},
                     "fields": [{"name": "count", "type": integer["type"]}], "methods": []}],
    }))
    arguments = ["inheritance-manifest", "--sv-declarations", str(sidecar),
                 "--sv-source", str(source), "--out", str(output)]
    assert main(arguments, out=StringIO()) == 0
    before = (output.read_bytes(), output.stat().st_mtime_ns)
    source.write_text(text.replace("count=seed;", "count=seed+1;"))
    assert main(arguments, out=StringIO()) == 0
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    old = "input int seed" if changed == "constructor" else "int count"
    source.write_text(text.replace(old, old.replace("int", "string")))
    with pytest.raises(SVXInheritanceError, match="does not match source type"):
        main(arguments, out=StringIO())
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_sv_body_edit_refreshes_integrated_copy_without_changing_python_bridge(tmp_path):
    pytest.importorskip('pyslang')
    source = tmp_path / 'owner.sv'
    source.write_text('package p; class A; int count; function new(input int seed); '
                      'count=seed; endfunction endclass endpackage\n')
    parameter = inheritance_parameter('seed', Int)
    sidecar = tmp_path / 'declarations.json'
    sidecar.write_text(json.dumps({
        'schema_uri': SV_DECLARATION_SCHEMA_URI,
        'schema_version': SV_DECLARATION_SCHEMA_VERSION,
        'classes': [{'canonical_id': 'sv://p/A', 'language': 'sv', 'symbol': 'p::A',
                     'constructor': {'initiator': 'python', 'parameters': [parameter]},
                     'fields': [{'name': 'count', 'type': parameter['type']}], 'methods': []}],
    }))
    manifest = tmp_path / 'manifest.json'
    discover = ['inheritance-manifest', '--sv-declarations', str(sidecar),
                '--sv-source', str(source), '--out', str(manifest)]
    generated = tmp_path / 'generated'
    generate = ['inheritance-gen', '--manifest', str(manifest), '--sv-source', str(source),
                '--python-out', str(generated / 'python'),
                '--sv-integrated-dir', str(generated / 'sv'),
                '--artifact-manifest', str(generated / 'artifacts.json')]
    assert main(discover, out=StringIO()) == 0
    assert main(generate, out=StringIO()) == 0
    before_manifest = (manifest.read_bytes(), manifest.stat().st_mtime_ns)
    python_files = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in (generated / 'python').rglob('*.py')}
    integrated = generated / 'sv' / 'source.sv'
    before_integrated = integrated.read_bytes()
    source.write_text(source.read_text().replace('count=seed;', 'count=seed+1;'))
    with pytest.raises((SystemExit, SVXInheritanceError), match='stale|changed'):
        main(generate + ['--check'], out=StringIO())
    assert integrated.read_bytes() == before_integrated
    assert main(discover, out=StringIO()) == 0
    assert (manifest.read_bytes(), manifest.stat().st_mtime_ns) == before_manifest
    assert main(generate, out=StringIO()) == 0
    assert integrated.read_bytes() != before_integrated
    assert b'count=seed+1;' in integrated.read_bytes()
    assert b'count=seed+1;' in source.read_bytes()
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in python_files} == python_files
    assert main(discover + ['--check'], out=StringIO()) == 0
    assert main(generate + ['--check'], out=StringIO()) == 0
