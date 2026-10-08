"""Constructor class/VIF handles use the same public value contract as methods."""

import json
import os
from pathlib import Path
import sys

import svtypes
from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def binding(annotation):
    codec = svtypes.materialize_type_spec(annotation, location="constructor handle test")
    return {
        "unified_type_name": svtypes.unified_type_name(codec),
        "svtypes": svtypes.type_spec_identity(annotation),
        "sv": svtypes.sv_type_expression(codec),
        "sv_packer": svtypes.sv_packer_expression(codec),
        "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict(),
    }


def manifest_data():
    data = field_manifest()
    base, derived = data["classes"]
    base.pop("fields")
    base["canonical_id"] = "sv://constructor_handle_pkg/Holder"
    base["symbol"] = "constructor_handle_pkg::Holder"
    packet_target = "sv://external_handle_test_pkg/Packet"
    vif_target = "sv-vif://external_bus_if/master"
    logic = binding(svtypes.Logic[8])
    operations = []
    for name, member, operation in (("read", "read", "function"),
                                    ("write_data", "data", "signal_write")):
        operations.append({
            "operation": operation, "member": member,
            "method": {
                "canonical_id": f"{vif_target}#{name}", "name": name,
                "parameters": [] if name == "read" else [{"name": "value", "type": logic}],
                "return_type": logic if name == "read" else "void", "timing": "function",
            },
        })
    if os.environ.get("SVX_CTOR_TRANSPORT_ONLY") == "1":
        operations = []
    base["constructor"] = {"initiator": "python", "parameters": [
        {"name": "packet", "type": binding(svtypes.RemoteRef[packet_target]),
         "handle": {"kind": "sv_class", "target_type_name": packet_target,
                    "sv_type": "external_handle_test_pkg::Packet"}},
        {"name": "vif", "type": binding(svtypes.RemoteRef[vif_target]),
         "handle": {"kind": "virtual_interface", "target_type_name": vif_target,
                    "sv_type": "virtual external_bus_if.master", "operations": operations}},
    ]}
    base["fields"] = [
        {"name": "native_" + parameter["name"], "type": parameter["type"],
         "handle": parameter["handle"]}
        for parameter in base["constructor"]["parameters"]
    ]
    if os.environ.get("SVX_DISCOVER_HANDLE_FIELDS") == "1":
        for field in base["fields"]:
            field.pop("handle")
    base["methods"] = [{
        "canonical_id": f"{base['canonical_id']}#read_value", "name": "read_value",
        "parameters": [], "return_type": binding(svtypes.Int), "timing": "function",
        "virtual": False, "pure_virtual": False,
    }]
    if os.environ.get("SVX_HANDLE_ALIAS_GROUPING") == "1":
        packet_parameter = base["constructor"]["parameters"][0]
        alias = {**packet_parameter["handle"], "sv_type": "constructor_handle_pkg::packet_alias_t"}
        base["methods"].append({
            "canonical_id": f"{base['canonical_id']}#echo_packet", "name": "echo_packet",
            "parameters": [{"name": "value", "type": packet_parameter["type"], "handle": alias}],
            "return_type": packet_parameter["type"], "return_handle": packet_parameter["handle"],
            "timing": "function", "virtual": False, "pure_virtual": False,
        })
    derived["canonical_id"] = "py://constructor_handles_user/Derived"
    derived["symbol"] = "constructor_handles_user.Derived"
    root_id = "py://tests/integration/constructor_handles_user/PlainHolder"
    data["classes"].append({
        "canonical_id": root_id, "language": "python",
        "symbol": "tests.integration.constructor_handles_user.PlainHolder",
        "constructor": base["constructor"],
        "methods": [{**base["methods"][0], "canonical_id": f"{root_id}#read_value", "virtual": True}],
    })
    return data


if __name__ == "__main__":
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest_data(), indent=2) + "\n")
