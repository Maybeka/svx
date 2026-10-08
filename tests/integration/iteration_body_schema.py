"""Unchanged boundary contract for two Python implementation revisions."""

import json
from pathlib import Path
import sys

from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def manifest_data():
    data = field_manifest()
    base, derived = data["classes"]
    binding = base.pop("fields")[0]["type"]
    base["constructor"]["parameters"] = [
        {"name": name, "type": binding}
        for name in ("ok", "request", "error", "request_value", "object_id", "svx_object_id")
    ]
    base["canonical_id"] = "sv://iteration_pkg/Driver"
    base["symbol"] = "iteration_pkg::Driver"
    base["methods"] = [
        {
            "canonical_id": f"{base['canonical_id']}#{name}", "name": name,
            "parameters": [{"name": "svx_return_value", "type": binding}],
            "return_type": binding, "timing": "function", "virtual": virtual,
            "pure_virtual": False,
        }
        for name, virtual in (("check", True), ("call_check", False))
    ]
    derived["canonical_id"] = "py://iteration_body_user/Derived"
    derived["symbol"] = "iteration_body_user.Derived"
    return data


if __name__ == "__main__":
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest_data(), indent=2) + "\n")
