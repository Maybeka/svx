"""Source-validated typedef and closed-specialization runtime fixture."""

import json
from pathlib import Path
import sys

from svtypes import Int, Logic
from svx.declarations import (
    SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION, inheritance_parameter,
)


def declarations():
    integer = inheritance_parameter("value", Int)["type"]
    logic = inheritance_parameter("value", Logic[8])
    return {
        "schema_uri": SV_DECLARATION_SCHEMA_URI,
        "schema_version": SV_DECLARATION_SCHEMA_VERSION,
        "classes": [{
            "canonical_id": "sv://signature_types_pkg/BaseInt8", "language": "sv",
            "symbol": "signature_types_pkg::Base",
            "specialization": {"arguments": [
                {"kind": "type", "type": integer},
                {"kind": "value", "sv_type": "int", "value": 8},
            ]},
            "constructor": {"initiator": "python", "parameters": [inheritance_parameter("seed", Int)]},
            "fields": [{"name": "count", "type": integer}],
            "methods": [{
                "canonical_id": "sv://signature_types_pkg/BaseInt8#check",
                "name": "check", "timing": "function", "virtual": True,
                "parameters": [logic], "return_type": integer,
            }],
        }, {
            "canonical_id": "sv://signature_types_pkg/Hosted", "language": "sv",
            "symbol": "signature_types_pkg::Hosted",
            "constructor": {"initiator": "sv", "parameters": [inheritance_parameter("seed", Int)]},
            "fields": [{"name": "count", "type": integer}],
            "methods": [{
                "canonical_id": "sv://signature_types_pkg/Hosted#check",
                "name": "check", "timing": "function", "virtual": True,
                "parameters": [logic], "return_type": integer,
            }],
        }],
    }


if __name__ == "__main__":
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(declarations(), indent=2) + "\n")
