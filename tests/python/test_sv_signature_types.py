from copy import deepcopy
from io import StringIO
import json

import pytest

from svx.errors import SVXInheritanceError
from svx.sv_scan import validate_sv_declarations


def declaration():
    return {"symbol": "p::A", "methods": [{
        "name": "check", "timing": "function",
        "parameters": [{"name": "value", "type": {"sv": "int"}}],
        "return_type": {"sv": "int"},
    }]}


@pytest.mark.parametrize("changed, location", [("parameter", "parameter value"), ("return", "return type")])
def test_source_signature_rejects_type_drift(tmp_path, changed, location):
    pytest.importorskip("pyslang")
    source = tmp_path / "types.sv"
    source.write_text("package p; class A; function int check(input int value); return value; "
                      "endfunction endclass endpackage\n")
    valid = declaration()
    validate_sv_declarations([valid], [source])
    wrong = deepcopy(valid)
    if changed == "parameter":
        wrong["methods"][0]["parameters"][0]["type"]["sv"] = "logic [7:0]"
    else:
        wrong["methods"][0]["return_type"]["sv"] = "string"
    with pytest.raises(SVXInheritanceError, match=location + ".*does not match"):
        validate_sv_declarations([wrong], [source])


def test_source_signature_accepts_semantically_matching_typedefs(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "aliases.sv"
    source.write_text("package p; typedef int count_t; class A; "
                      "function count_t check(input count_t value); return value; "
                      "endfunction endclass endpackage\n")
    validate_sv_declarations([declaration()], [source])


def test_source_signature_uses_closed_specialization(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "specialized.sv"
    source.write_text("package p; class A #(type T=int, int N=4); "
                      "function T check(input logic[N-1:0] value); return T'(value); "
                      "endfunction endclass endpackage\n")
    valid = declaration()
    valid["specialization"] = {"arguments": [
        {"kind": "type", "type": {"sv": "int"}}, {"kind": "value", "value": 8},
    ]}
    valid["methods"][0]["parameters"][0]["type"]["sv"] = "logic [7:0]"
    validate_sv_declarations([valid], [source])
    valid["methods"][0]["parameters"][0]["type"]["sv"] = "logic [3:0]"
    with pytest.raises(SVXInheritanceError, match="parameter value.*does not match"):
        validate_sv_declarations([valid], [source])


def test_source_signature_resolves_inherited_imported_types_and_native_handles(tmp_path):
    pytest.importorskip("pyslang")
    types = tmp_path / "types.sv"
    source = tmp_path / "methods.sv"
    types.write_text("package types; typedef int count_t; class Packet; endclass endpackage\n")
    source.write_text(
        "package p; import types::*; class A; "
        "function count_t check(input count_t value); return value; endfunction "
        "function Packet echo(input Packet value); return value; endfunction "
        "endclass class Child extends A; endclass endpackage\n"
    )
    valid = declaration()
    valid["symbol"] = "p::Child"
    valid["methods"].append({
        "name": "echo", "timing": "function",
        "parameters": [{"name": "value", "type": {"sv": "longint unsigned"},
                        "handle": {"sv_type": "types::Packet"}}],
        "return_type": {"sv": "longint unsigned"},
        "return_handle": {"sv_type": "types::Packet"},
    })
    validate_sv_declarations([valid], [types, source])
    valid["methods"][1]["parameters"][0]["handle"]["sv_type"] = "p::A"
    with pytest.raises(SVXInheritanceError, match="parameter value.*does not match"):
        validate_sv_declarations([valid], [types, source])


def test_source_signature_missing_type_dependency_is_not_silently_accepted(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "missing.sv"
    source.write_text("package p; class A; function absent_t check(input absent_t value); "
                      "endfunction endclass endpackage\n")
    with pytest.raises(SVXInheritanceError, match="cannot resolve.*type dependencies"):
        validate_sv_declarations([declaration()], [source])


def test_source_signature_checks_same_path_after_type_edit(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "edit.sv"
    def write(sv_type):
        source.write_text(f"package p; class A; function int check(input {sv_type} value); "
                          "return 0; endfunction endclass endpackage\n")
    write("int")
    validate_sv_declarations([declaration()], [source])
    write("string")
    with pytest.raises(SVXInheritanceError, match="parameter value.*does not match"):
        validate_sv_declarations([declaration()], [source])


def test_source_signature_checks_expanded_ancestor_declarations(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "ancestors.sv"
    source.write_text("package p; class A; function int check(input int value); return value; "
                      "endfunction endclass class Child extends A; endclass endpackage\n")
    ancestor = declaration()
    child = {"symbol": "p::Child", "methods": [], "base_lineage": [ancestor]}
    validate_sv_declarations([child], [source])
    ancestor["methods"][0]["parameters"][0]["type"]["sv"] = "string"
    with pytest.raises(SVXInheritanceError, match="p::A.check parameter value.*does not match"):
        validate_sv_declarations([child], [source])


def test_manifest_cli_type_failure_preserves_previous_output(tmp_path):
    pytest.importorskip("pyslang")
    from svtypes import Int
    from svx.cli import main
    from svx.declarations import (
        SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION, inheritance_parameter,
    )
    source = tmp_path / "source.sv"
    sidecar = tmp_path / "declarations.json"
    output = tmp_path / "manifest.json"
    source.write_text("package p; class A; function int check(input int value); return value; "
                      "endfunction endclass endpackage\n")
    data = declaration()
    data.update(canonical_id="sv://p/A", language="sv")
    method = data["methods"][0]
    method["canonical_id"] = "sv://p/A#check"
    method["virtual"] = False
    method["parameters"] = [inheritance_parameter("value", Int)]
    method["return_type"] = method["parameters"][0]["type"]
    sidecar.write_text(json.dumps({
        "schema_uri": SV_DECLARATION_SCHEMA_URI,
        "schema_version": SV_DECLARATION_SCHEMA_VERSION, "classes": [data],
    }))
    arguments = ["inheritance-manifest", "--sv-declarations", str(sidecar),
                 "--sv-source", str(source), "--out", str(output)]
    assert main(arguments, out=StringIO()) == 0
    before = (output.read_bytes(), output.stat().st_mtime_ns)
    source.write_text(source.read_text().replace("return value;", "return value + 1;"))
    assert main(arguments, out=StringIO()) == 0
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    source.write_text(source.read_text().replace("input int value", "input string value"))
    messages = StringIO()
    with pytest.raises(SVXInheritanceError, match="parameter value.*does not match"):
        main(arguments, out=messages)
    assert messages.getvalue() == ""
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_signature_probe_does_not_collide_with_empty_user_package(tmp_path):
    pytest.importorskip("pyslang")
    source = tmp_path / "names.sv"
    source.write_text("package svx_signature_probe; endpackage "
                      "package p; class A; function int check(input int value); return value; "
                      "endfunction endclass endpackage\n")
    validate_sv_declarations([declaration()], [source])
