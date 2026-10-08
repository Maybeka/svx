"""Field-projection fixture with legal bridge-name collisions in SV formals."""

import copy
import argparse
import json
from pathlib import Path


def manifest_data(*, legacy_assoc_factory=False):
    data = json.loads(Path(__file__).with_name("field_projection_inheritance_manifest.json").read_text())
    binding = data["classes"][1]["fields"][0]["type"]
    methods = [
        {
            "canonical_id": f"sv://field_pkg/Base#{name}",
            "name": name,
            "parameters": [
                {"name": parameter, "type": copy.deepcopy(binding)}
                for parameter in ("self", "svx_self", "invoke_sv", "svx_invoke_sv",
                                  "invoke_sv_static", "svx_invoke_sv_static")
            ],
            "return_type": copy.deepcopy(binding),
            "timing": "function",
            "virtual": False,
            "static": static,
        }
        for name, static in (("collisions", False), ("collisions_static", True))
    ]
    data["classes"][0]["methods"] = methods
    data["classes"][2]["base_lineage"][0]["methods"] = copy.deepcopy(methods)
    constructor = {"initiator": "sv", "parameters": [
        {"name": parameter, "type": copy.deepcopy(binding)}
        for parameter in ("self", "svx_self", "_native", "encode_constructor",
                          "bind_instance", "object_id", "SVMirror", "svx_object_id")
    ]}
    data["classes"][0]["constructor"] = constructor
    data["classes"][2]["base_lineage"][0]["constructor"] = copy.deepcopy(constructor)
    if legacy_assoc_factory:
        for cls in data['classes']:
            for owner in (cls, *cls.get('base_lineage', [])):
                for field in owner.get('fields', []):
                    if field['name'] == 'mapping':
                        field['type'].pop('svtypes', None)
                        field['type']['python'] = {
                            'module': 'tests.integration.field_projection_types',
                            'symbol': 'int_to_int', 'args': [], 'kwargs': {},
                        }
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--legacy-assoc-factory', action='store_true')
    args = parser.parse_args()
    args.output.write_text(json.dumps(manifest_data(legacy_assoc_factory=args.legacy_assoc_factory), indent=2) + "\n")
