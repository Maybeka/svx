import json

import svtypes
from svx.declarations import inheritance_parameter, sv_class_handle
from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest

SV_ID = "sv://natural_bridge_pkg/A"
PY_ID = "py://tests/integration/natural_constructor_bridge/B"


def manifest_data():
    data = field_manifest()
    source = data["classes"][0]
    source.update(canonical_id=SV_ID, symbol="natural_bridge_pkg::A", methods=[])
    source["constructor"]["parameters"] = [
        inheritance_parameter("seed", svtypes.Int), inheritance_parameter("label", svtypes.String),
        inheritance_parameter("packet", svtypes.RemoteRef["sv://natural_bridge_pkg/Packet"],
                              handle=sv_class_handle("sv://natural_bridge_pkg/Packet", "natural_bridge_pkg::Packet"))]
    return data


if __name__ == "__main__":
    print(json.dumps(manifest_data()))
