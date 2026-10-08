"""Public type/value specialization fixture, including field and virtual dispatch."""

import json
from pathlib import Path
import sys

from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def manifest_data():
    data = field_manifest()
    base, derived = data["classes"]
    old_id = base["canonical_id"]
    base["canonical_id"] = "sv://parameterized_pkg/BaseInt7"
    base["symbol"] = "parameterized_pkg::Base"
    binding = base["fields"][0]["type"]
    base["specialization"] = {"arguments": [
        {"kind": "type", "type": binding},
        {"kind": "value", "sv_type": "int", "value": 7},
    ]}
    for method in base["methods"]:
        method["canonical_id"] = method["canonical_id"].replace(old_id, base["canonical_id"])
    for name, virtual in (("check", True), ("call_check", False)):
        base["methods"].append({
            "canonical_id": f"{base['canonical_id']}#{name}",
            "name": name, "parameters": [{"name": "value", "type": binding}],
            "return_type": binding, "timing": "function", "virtual": virtual,
            "pure_virtual": False,
        })
    base["methods"].extend([
        {
            "canonical_id": f"{base['canonical_id']}#collisions",
            "name": "collisions",
            "parameters": [
                {"name": name, "type": binding}
                for name in ("ok", "request", "response", "error", "bytes", "offset", "request_value", "response_value", "svx_ok")
            ] + [{"name": "result", "direction": "output", "type": binding}],
            "return_type": binding, "timing": "function", "virtual": True,
            "pure_virtual": False,
        },
        {
            "canonical_id": f"{base['canonical_id']}#call_collisions",
            "name": "call_collisions", "parameters": [],
            "return_type": binding, "timing": "function", "virtual": False,
            "pure_virtual": False,
        },
        {
            "canonical_id": f"{base['canonical_id']}#observe",
            "name": "observe", "parameters": [{"name": "result", "direction": "output", "type": binding}],
            "return_type": "void", "timing": "function", "virtual": True,
            "pure_virtual": False,
        },
        {
            "canonical_id": f"{base['canonical_id']}#call_observe",
            "name": "call_observe", "parameters": [],
            "return_type": binding, "timing": "function", "virtual": False,
            "pure_virtual": False,
        },
    ])
    derived["canonical_id"] = "py://tests/integration/parameterized_mirror/Derived"
    derived["symbol"] = "tests.integration.parameterized_mirror_test.Derived"
    return data


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest_data(), indent=2) + "\n", encoding="utf-8")
