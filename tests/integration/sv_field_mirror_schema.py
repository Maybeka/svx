"""Build deterministic input metadata for the inherited SV-field regression."""

import json
import argparse
from pathlib import Path

import svtypes


def manifest_data(*, include_shadowing_fields=False, include_four_state=False,
                  include_nested_fields=False):
    codec = svtypes.Int()
    binding = {
        "unified_type_name": svtypes.unified_type_name(codec),
        "svtypes": svtypes.type_spec_identity(svtypes.Int),
        "sv": svtypes.sv_type_expression(codec),
        "sv_packer": svtypes.sv_packer_expression(codec),
        "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict(),
    }
    base = {
        "canonical_id": "sv://field_owner_pkg/Base",
        "language": "sv",
        "symbol": "field_owner_pkg::Base",
        "constructor": {"initiator": "python", "parameters": []},
        "fields": [{"name": "count", "type": binding}],
        "methods": [{
            "canonical_id": "sv://field_owner_pkg/Base#get_count",
            "name": "get_count", "parameters": [], "return_type": binding,
            "timing": "function", "virtual": False, "pure_virtual": False,
        }, {
            "canonical_id": "sv://field_owner_pkg/Base#set_count",
            "name": "set_count", "parameters": [{"name": "value", "type": binding}],
            "return_type": "void", "timing": "function", "virtual": False,
            "pure_virtual": False,
        }],
    }
    if include_four_state:
        flags = svtypes.Logic[4]()
        flags_binding = {
            'unified_type_name': svtypes.unified_type_name(flags),
            'svtypes': svtypes.type_spec_identity(svtypes.Logic[4]),
            'sv': svtypes.sv_type_expression(flags),
            'sv_packer': svtypes.sv_packer_expression(flags),
            'encoding_descriptor': svtypes.encoding_descriptor(flags).to_dict(),
        }
        base['fields'].append({'name': 'flags', 'type': flags_binding})
        base['methods'].extend([{
            'canonical_id': 'sv://field_owner_pkg/Base#get_flags',
            'name': 'get_flags', 'parameters': [], 'return_type': flags_binding,
            'timing': 'function', 'virtual': False, 'pure_virtual': False,
        }, {
            'canonical_id': 'sv://field_owner_pkg/Base#set_flags',
            'name': 'set_flags', 'parameters': [{'name': 'value', 'type': flags_binding}],
            'return_type': 'void', 'timing': 'function', 'virtual': False,
            'pure_virtual': False,
        }])
    if include_shadowing_fields:
        base['fields'].extend(
            {'name': name, 'type': binding}
            for name in ('bytes', 'field_offset', 'field_value', 'error', 'ok', 'response')
        )
        queue = svtypes.Queue[svtypes.Int]()
        base['fields'].append({'name': 'operation', 'type': {
            'unified_type_name': svtypes.unified_type_name(queue),
            'svtypes': svtypes.type_spec_identity(svtypes.Queue[svtypes.Int]),
            'sv': svtypes.sv_type_expression(queue),
            'sv_packer': svtypes.sv_packer_expression(queue),
            'encoding_descriptor': svtypes.encoding_descriptor(queue).to_dict(),
        }})
        fixed = svtypes.Array[svtypes.Int, 3]()
        base['fields'].append({'name': 'fixed_values', 'type': {
            'unified_type_name': svtypes.unified_type_name(fixed),
            'svtypes': svtypes.type_spec_identity(svtypes.Array[svtypes.Int, 3]),
            'sv': svtypes.sv_type_expression(fixed),
            'sv_packer': svtypes.sv_packer_expression(fixed),
            'encoding_descriptor': svtypes.encoding_descriptor(fixed).to_dict(),
        }})
    if include_nested_fields:
        for name, annotation in (
            ('nested_values', svtypes.Queue[svtypes.Queue[svtypes.Int]]),
            ('nested_dynamic', svtypes.DynArray[svtypes.DynArray[svtypes.Int]]),
            ('keyed_values', svtypes.AssocArray[svtypes.String, svtypes.Queue[svtypes.Int]]),
            ('fixed_matrix', svtypes.Array[svtypes.Array[svtypes.Int, 2], 2]),
        ):
            nested = annotation()
            base['fields'].append({'name': name, 'type': {
                'unified_type_name': svtypes.unified_type_name(nested),
                'svtypes': svtypes.type_spec_identity(annotation),
                'sv': svtypes.sv_type_expression(nested),
                'sv_packer': svtypes.sv_packer_expression(nested),
                'encoding_descriptor': svtypes.encoding_descriptor(nested).to_dict(),
            }})
        from tests.integration.field_projection_types import deep_record
        record = deep_record()
        base['fields'].append({'name': 'record', 'type': {
            'unified_type_name': svtypes.unified_type_name(record),
            'python': {'module': 'tests.integration.field_projection_types',
                       'symbol': 'deep_record', 'args': [], 'kwargs': {}},
            'sv': svtypes.sv_type_expression(record),
            'sv_packer': svtypes.sv_packer_expression(record),
            'encoding_descriptor': svtypes.encoding_descriptor(record).to_dict(),
        }})
    return {
        "schema_uri": "https://svx.dev/schema/inheritance-manifest/v2",
        "schema_version": "2.0.0", "generator_abi_version": 2,
        "required_runtime_capabilities": [
            "svtypes.checked-encoding-descriptor.v1", "svtypes.codec-context.v1",
            "svtypes.record-schema.v1", "svtypes.remote-reference.v1",
            "svtypes.external-field-storage.v1",
        ],
        "classes": [base, {
            "canonical_id": "py://tests/integration/sv_field_mirror/Derived",
            "language": "python", "symbol": "tests.integration.sv_field_mirror_test.Derived",
            "methods": [], "base_lineage": [base],
        }],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--nested-fields', action='store_true')
    args = parser.parse_args()
    target = args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    from tests.integration.field_projection_types import DeepFieldRecord
    (target.parent / 'record.sv').write_text(DeepFieldRecord.to_sv_obj() + '\n')
    target.write_text(json.dumps(manifest_data(include_shadowing_fields=True,
                                             include_nested_fields=args.nested_fields), indent=2) + "\n", encoding="utf-8")
