"""Declare pure-virtual function/task contracts using public SvTypes types."""

import json
from pathlib import Path
import sys

from svtypes import Int
from svx.declarations import inheritance_parameter
from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def manifest_data():
    data = field_manifest()
    binding = inheritance_parameter('value', Int)['type']
    base = {
        'canonical_id': 'sv://pure_virtual_pkg/Base',
        'language': 'sv', 'symbol': 'pure_virtual_pkg::Base',
        'constructor': {'initiator': 'python', 'parameters': []},
        'methods': [{
            'canonical_id': 'sv://pure_virtual_pkg/Base#check',
            'name': 'check', 'timing': 'function', 'virtual': True, 'pure_virtual': True,
            'parameters': [inheritance_parameter('value', Int)], 'return_type': binding,
        }, {
            'canonical_id': 'sv://pure_virtual_pkg/Base#update',
            'name': 'update', 'timing': 'task', 'virtual': True, 'pure_virtual': True,
            'parameters': [inheritance_parameter('delta', Int),
                           inheritance_parameter('value', Int, direction='inout'),
                           inheritance_parameter('observed', Int, direction='output')],
            'return_type': 'void',
        }],
    }
    data['classes'] = [base, {
        'canonical_id': 'py://tests/integration/pure_virtual/Derived',
        'language': 'python', 'symbol': 'tests.integration.pure_virtual_test.Derived',
        'methods': [], 'base_lineage': [base],
    }]
    return data


if __name__ == '__main__':
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest_data(), indent=2) + '\n', encoding='utf-8')
