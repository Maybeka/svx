from copy import deepcopy

import pytest

from svx.errors import SVXInheritanceError
from svx.sv_scan import validate_sv_declarations


def declaration():
    return {"symbol": "p::A", "methods": [],
            "constructor": {"parameters": [{"name": "seed", "type": {"sv": "int"}}]},
            "fields": [{"name": "count", "type": {"sv": "int"}}]}


def source_file(tmp_path, text=None):
    pytest.importorskip("pyslang")
    source = tmp_path / "source.sv"
    source.write_text(text or (
        "package p; typedef int count_t; class A; count_t count; "
        "function new(input count_t seed=4); count=seed; endfunction endclass endpackage\n"
    ))
    return source


@pytest.mark.parametrize("member", ["constructor", "field"])
def test_semantic_constructor_and_field_types_reject_drift(tmp_path, member):
    source = source_file(tmp_path)
    valid = declaration()
    validate_sv_declarations([valid], [source])
    wrong = deepcopy(valid)
    parameter = wrong["constructor"]["parameters"][0] if member == "constructor" else wrong["fields"][0]
    parameter["type"]["sv"] = "logic [7:0]"
    with pytest.raises(SVXInheritanceError, match="does not match source type"):
        validate_sv_declarations([wrong], [source])


@pytest.mark.parametrize("change", ["count", "name", "direction"])
def test_constructor_formal_contract(tmp_path, change):
    source = source_file(tmp_path)
    wrong = declaration()
    if change == "count":
        wrong["constructor"]["parameters"] = []
    elif change == "name":
        wrong["constructor"]["parameters"][0]["name"] = "other"
    else:
        wrong["constructor"]["parameters"][0]["direction"] = "output"
    with pytest.raises(SVXInheritanceError, match="p::A.new.*(requires|expects)"):
        validate_sv_declarations([wrong], [source])


def test_implicit_constructor_does_not_inherit_parent_formals(tmp_path):
    source = source_file(tmp_path,
        "package p; class Parent; int count; function new(input int seed=4); "
        "count=seed; endfunction endclass class A extends Parent; endclass endpackage\n")
    valid = declaration()
    valid["constructor"]["parameters"] = []
    validate_sv_declarations([valid], [source])


def test_closed_specialization_constructor_and_fields(tmp_path):
    source = source_file(tmp_path,
        "package p; class A #(type T=int, int N=4); T count; logic[N-1:0] data; "
        "function new(input T seed); endfunction endclass endpackage\n")
    valid = declaration()
    valid["specialization"] = {"arguments": [
        {"kind": "type", "type": {"sv": "int"}}, {"kind": "value", "value": 8},
    ]}
    valid["fields"].append({"name": "data", "type": {"sv": "logic [7:0]"}})
    validate_sv_declarations([valid], [source])
    valid["fields"][1]["type"]["sv"] = "logic [3:0]"
    with pytest.raises(SVXInheritanceError, match="data field type.*does not match"):
        validate_sv_declarations([valid], [source])


def test_native_class_field_matches_static_handle_type_not_carrier(tmp_path):
    source = source_file(tmp_path,
        "package p; class Packet; endclass class A; Packet item; endclass endpackage\n")
    valid = {"symbol": "p::A", "fields": [{"name": "item", "type": {"sv": "longint unsigned"},
                                              "handle": {"sv_type": "p::Packet"}}]}
    validate_sv_declarations([valid], [source])
    valid["fields"][0]["handle"]["sv_type"] = "p::A"
    with pytest.raises(SVXInheritanceError, match="item field type.*does not match"):
        validate_sv_declarations([valid], [source])


def test_vif_constructor_and_field_use_the_static_modport_type(tmp_path):
    source = source_file(tmp_path,
        "interface bus; logic data; modport master(output data); endinterface "
        "package p; class A; virtual bus.master port; "
        "function new(input virtual bus.master value); endfunction endclass endpackage\n")
    handle = {"sv_type": "virtual bus.master"}
    binding = {"sv": "longint unsigned"}
    valid = {"symbol": "p::A", "constructor": {"parameters": [
        {"name": "value", "type": binding, "handle": handle}]},
        "fields": [{"name": "port", "type": binding, "handle": handle}]}
    validate_sv_declarations([valid], [source])
    valid["fields"][0]["handle"] = {"sv_type": "virtual bus"}
    with pytest.raises(SVXInheritanceError, match="port field type.*does not match"):
        validate_sv_declarations([valid], [source])


def test_standalone_sv_field_target_emits_a_bound_mirror_not_an_empty_view():
    from pathlib import PurePosixPath
    from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest
    from tests.integration.sv_field_mirror_schema import manifest_data
    data = manifest_data()
    data["classes"] = data["classes"][:1]
    manifest = parse_manifest(data)
    python = emit_python_mirrors(manifest)
    text = python[PurePosixPath("svx_mirror/field_owner_pkg.py")]
    assert "class Base(SVMirror):" in text
    assert "count = _codec_from_spec(" in text
    assert "sv://field_owner_pkg/Base.count" in text
    assert "_svx_bind_active_projected_fields()" in text
    assert len(manifest.classes) == 1
    assert "class Derived" not in emit_sv_mirrors(manifest)


def test_sv_origin_standalone_field_target_allows_python_mirror_construction():
    from pathlib import PurePosixPath
    from svx.inheritance import emit_python_mirrors, emit_sv_mirrors, parse_manifest
    from tests.integration.sv_field_mirror_schema import manifest_data
    data = manifest_data()
    data["classes"] = data["classes"][:1]
    data["classes"][0]["constructor"]["initiator"] = "sv"
    manifest = parse_manifest(data)
    text = emit_python_mirrors(manifest)[PurePosixPath("svx_mirror/field_owner_pkg.py")]
    assert "class Base(SVMirror):" in text
    assert "count = _codec_from_spec(" in text
    assert "must be created by SV" not in text
    assert "inheritance_create_sv(" in text
    assert text.index("instance._svx_bind_active_projected_fields()") < text.index("cls.__init__(instance, *args)")
    sv = emit_sv_mirrors(manifest)
    assert "class Base extends field_owner_pkg::Base" in sv
    assert 'sv://field_owner_pkg/Base.count@svx_field_read' in sv
    assert "int count;" not in sv  # Inherited storage must not be shadowed.


def test_inherited_native_field_discovery_uses_declaring_package(tmp_path):
    from svx.declarations import _enrich_native_handle_fields
    source = source_file(tmp_path,
        "package parent; class Packet; endclass class A; Packet item; endclass endpackage "
        "package child; class Packet; endclass class Child extends parent::A; endclass endpackage\n")
    data = [{"language": "sv", "symbol": "child::Child", "fields": [{
        "name": "item", "type": {"sv": "longint unsigned"},
    }]}]
    # Supply a real RemoteRef declaration rather than inferring a carrier codec.
    from svtypes import RemoteRef
    from svx.declarations import inheritance_parameter
    data[0]["fields"][0]["type"] = inheritance_parameter("item", RemoteRef["sv://parent/Packet"])["type"]
    _enrich_native_handle_fields(data, [source])
    assert data[0]["fields"][0]["handle"]["sv_type"] == "parent::Packet"
