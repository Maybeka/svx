from io import StringIO
import json

import pytest

from svtypes import RemoteRef
from svx.cli import main
from svx.declarations import SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION, inheritance_parameter
from svx.errors import SVXInheritanceError


def inputs(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "source.sv"
    source.write_text(
        "package types; class Packet #(int N=8); endclass typedef Packet#(8) packet_t; endpackage "
        "package p; import types::*; class A; packet_t item; "
        "function new(input packet_t packet); item=packet; endfunction "
        "function packet_t echo(input Packet#(8) value); return value; endfunction endclass endpackage\n")
    value = inheritance_parameter("packet", RemoteRef["sv://types/Packet8"])
    def handle(sv_type):
        return {"kind": "sv_class", "target_type_name": "sv://types/Packet8", "sv_type": sv_type}
    sidecar = tmp_path / "declarations.json"
    sidecar.write_text(json.dumps({"schema_uri": SV_DECLARATION_SCHEMA_URI,
                                  "schema_version": SV_DECLARATION_SCHEMA_VERSION, "classes": [{
        "canonical_id": "sv://p/A", "language": "sv", "symbol": "p::A",
        "constructor": {"initiator": "python", "parameters": [{**value, "handle": handle("types::packet_t")}]},
        "fields": [{"name": "item", "type": value["type"]}],
        "methods": [{"canonical_id": "sv://p/A#echo", "name": "echo", "timing": "function",
                     "virtual": False, "parameters": [{**value, "name": "value", "handle": handle("types::Packet")}],
                     "return_type": value["type"], "return_handle": handle("types::packet_t")}],
    }]}))
    return source, sidecar


def test_equivalent_field_constructor_parameter_and_return_types_share_one_endpoint(tmp_path):
    source, sidecar = inputs(tmp_path)
    manifest = tmp_path / "manifest.json"
    assert main(["inheritance-manifest", "--sv-declarations", str(sidecar),
                 "--sv-source", str(source), "--out", str(manifest)], out=StringIO()) == 0
    assert main(["inheritance-gen", "--manifest", str(manifest), "--sv-source", str(source),
                 "--python-out", str(tmp_path / "python"), "--sv-out", str(tmp_path / "mirrors.sv")],
                out=StringIO()) == 0
    result = json.loads(manifest.read_text())["classes"][0]
    handles = [result["fields"][0]["handle"], result["constructor"]["parameters"][0]["handle"],
               result["methods"][0]["parameters"][0]["handle"], result["methods"][0]["return_handle"]]
    assert {handle["sv_type"] for handle in handles} == {"types::Packet#(8)"}


def test_alias_only_edit_is_noop_and_incompatible_specialization_preserves_manifest(tmp_path):
    source, sidecar = inputs(tmp_path)
    manifest = tmp_path / "manifest.json"
    args = ["inheritance-manifest", "--sv-declarations", str(sidecar),
            "--sv-source", str(source), "--out", str(manifest)]
    assert main(args, out=StringIO()) == 0
    before = manifest.read_bytes(), manifest.stat().st_mtime_ns
    data = json.loads(sidecar.read_text())
    data["classes"][0]["constructor"]["parameters"][0]["handle"]["sv_type"] = "types::Packet#(8)"
    sidecar.write_text(json.dumps(data))
    assert main(args, out=StringIO()) == 0
    assert (manifest.read_bytes(), manifest.stat().st_mtime_ns) == before
    data["classes"][0]["constructor"]["parameters"][0]["handle"]["sv_type"] = "types::Packet#(4)"
    sidecar.write_text(json.dumps(data))
    with pytest.raises(SVXInheritanceError, match="one foreign handle target.*static SV type"):
        main(args, out=StringIO())
    assert (manifest.read_bytes(), manifest.stat().st_mtime_ns) == before


def test_python_origin_contracts_and_ancestor_metadata_normalize_together(tmp_path):
    from svx.sv_scan import normalize_sv_handle_types
    source, _ = inputs(tmp_path)
    def handle(spelling):
        return {"kind": "sv_class", "target_type_name": "sv://types/Packet8", "sv_type": spelling}
    parent = {"language": "python", "symbol": "user.Root", "methods": [{
        "parameters": [{"handle": handle("types::packet_t")}], "return_handle": handle("types::Packet")}]}
    child = {"language": "python", "symbol": "user.Child", "base_lineage": [parent],
             "constructor": {"parameters": [{"handle": handle("types::Packet#(8)")}]}}
    normalize_sv_handle_types([child], [source])
    assert parent["methods"][0]["return_handle"]["sv_type"] == "types::Packet#(8)"
    parent["methods"][0]["return_handle"]["sv_type"] = "types::Packet#(4)"
    with pytest.raises(SVXInheritanceError, match="one foreign handle target"):
        normalize_sv_handle_types([child], [source])
    assert parent["methods"][0]["return_handle"]["sv_type"] == "types::Packet#(4)"
