import json
import svtypes
from svx.declarations import inheritance_parameter
from tests.integration.natural_constructor_bridge_schema import manifest_data as baseline, PY_ID


def manifest_data():
    data = baseline()
    root = data["classes"][0]
    parameters = root["constructor"]["parameters"]
    python = {
        "canonical_id": PY_ID, "language": "python",
        "symbol": "tests.integration.natural_constructor_bridge.B",
        "constructor": {"initiator": "sv", "parameters": [
            *parameters, inheritance_parameter("bias", svtypes.Int)]},
        "fields": [{"name": "local_value", "type": root["fields"][0]["type"]}],
        "methods": [],
    }
    data["classes"] = [{
        "canonical_id": "sv://natural_bridge_child_pkg/C", "language": "sv",
        "symbol": "natural_bridge_child_pkg::C",
        "constructor": {"initiator": "python", "parameters": parameters},
        "fields": [], "methods": [], "base_lineage": [root, python],
    }]
    return data


if __name__ == "__main__":
    print(json.dumps(manifest_data()))
