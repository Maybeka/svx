"""A timed native method with copy-out parameters and a static counterpart."""

import json
from pathlib import Path
import sys

from tests.integration.sv_field_mirror_schema import manifest_data as base_manifest


def manifest_data():
    data = base_manifest()
    base, derived = data["classes"]
    binding = base["fields"][0]["type"]
    base.pop("fields")
    base["canonical_id"] = "sv://inheritance_disable_pkg/Worker"
    base["symbol"] = "inheritance_disable_pkg::Worker"
    base["methods"] = [
        {"canonical_id": base["canonical_id"] + "#" + name, "name": name,
         "parameters": [{"name": "changed", "type": binding, "direction": "inout"},
                        {"name": "observed", "type": binding, "direction": "output"}],
         "return_type": "void", "timing": "task", "virtual": False,
         "static": static}
        for name, static in (("wait_value", False), ("wait_static", True),
                             ("wait_through_python", False), ("hook", False))
    ]
    base["methods"][-1]["virtual"] = True
    derived["canonical_id"] = "py://tests/integration/inheritance_disable/Derived"
    derived["symbol"] = "tests.integration.inheritance_disable_test.Derived"
    return data


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(manifest_data(), indent=2) + "\n")
