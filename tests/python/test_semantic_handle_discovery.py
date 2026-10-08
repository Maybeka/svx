from copy import deepcopy
from io import StringIO
import json

import pytest

from svtypes import Int, Object, RemoteRef, SvObject, svobj
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION,
    _enrich_native_handle_fields, inheritance_parameter,
)
from svx.errors import SVXInheritanceError


@svobj
class ValueItem(SvObject):
    count = Int()


def field(name, target):
    return {"name": name, "type": inheritance_parameter(name, RemoteRef[target])["type"]}


def source_file(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "source.sv"
    source.write_text(
        "interface bus; logic d; modport master(output d); endinterface "
        "package types; class Packet #(int N=4); endclass "
        "typedef Packet#(8) packet_t; typedef virtual bus.master bus_t; "
        "class Parent; packet_t item; bus_t port; endclass endpackage "
        "package p; import types::*; class A extends Parent; endclass endpackage\n"
    )
    return source


def declaration():
    return {"language": "sv", "symbol": "p::A", "fields": [
        field("item", "sv://types/Packet8"), field("port", "sv-vif://bus/master")], "methods": []}


def test_discovery_resolves_inherited_imported_aliases_and_closed_handles(tmp_path):
    source = source_file(tmp_path)
    data = [declaration()]
    _enrich_native_handle_fields(data, iter([source]))
    assert data[0]["fields"][0]["handle"] == {
        "kind": "sv_class", "target_type_name": "sv://types/Packet8", "sv_type": "types::Packet#(8)"}
    assert data[0]["fields"][1]["handle"]["sv_type"] == "virtual bus.master"
    assert len(data) == 1


def test_equivalent_explicit_alias_is_accepted_but_wrong_specialization_rejected(tmp_path):
    source = source_file(tmp_path)
    data = declaration()
    data["fields"][0]["handle"] = {
        "kind": "sv_class", "target_type_name": "sv://types/Packet8", "sv_type": "types::packet_t"}
    _enrich_native_handle_fields([data], [source])
    assert data["fields"][0]["handle"]["sv_type"] == "types::packet_t"
    wrong = deepcopy(data)
    wrong["fields"][0]["handle"]["sv_type"] = "types::Packet#(4)"
    with pytest.raises(SVXInheritanceError, match="item.*source type"):
        _enrich_native_handle_fields([wrong], [source])


def test_manifest_cli_discovers_handle_before_comparing_wire_carrier(tmp_path):
    from svx.cli import main
    source = source_file(tmp_path)
    sidecar = tmp_path / "declarations.json"
    output = tmp_path / "manifest.json"
    data = declaration()
    data["canonical_id"] = "sv://p/A"
    sidecar.write_text(json.dumps({"schema_uri": SV_DECLARATION_SCHEMA_URI,
                                  "schema_version": SV_DECLARATION_SCHEMA_VERSION,
                                  "classes": [data]}))
    args = ["inheritance-manifest", "--sv-declarations", str(sidecar),
            "--sv-source", str(source), "--out", str(output)]
    assert main(args, out=StringIO()) == 0
    result = json.loads(output.read_text())
    assert len(result["classes"]) == 1
    assert result["classes"][0]["fields"][0]["handle"]["sv_type"] == "types::Packet#(8)"
    before = output.read_bytes(), output.stat().st_mtime_ns
    assert main(args, out=StringIO()) == 0
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_by_value_svtypes_object_field_is_not_reclassified_as_a_native_handle(tmp_path):
    source = source_file(tmp_path)
    data = declaration()
    data["fields"] = [{"name": "item", "type": inheritance_parameter("item", Object[ValueItem])["type"]}]
    _enrich_native_handle_fields([data], [source])
    assert "handle" not in data["fields"][0]


def test_handle_type_parameter_uses_the_closed_source_specialization(tmp_path):
    source = source_file(tmp_path)
    source.write_text(source.read_text().replace(
        "class A extends Parent; endclass", "class A #(type T=types::packet_t); T item; endclass"))
    data = declaration()
    data["fields"] = [field("item", "sv://types/Packet8")]
    data["specialization"] = {"arguments": [{"kind": "type", "type": {"sv": "types::packet_t"}}]}
    _enrich_native_handle_fields([data], [source])
    assert data["fields"][0]["handle"]["sv_type"] == "types::Packet#(8)"
