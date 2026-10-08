"""Keep the full alternating fixture while adding class-owned static methods."""

import json
from pathlib import Path
import svtypes
from svx.declarations import _svtypes_binding


def manifest_data():
    data = json.loads(Path(__file__).with_name('alternating_chain_manifest.json').read_text())
    binding = _svtypes_binding(svtypes.Int, where='static scale')
    for source in data['classes'][0]['base_lineage'][1:]:
        source['methods'].append({
            'canonical_id': source['canonical_id'] + '#scale', 'name': 'scale',
            'parameters': [{'name': 'delta', 'type': binding}], 'return_type': binding,
            'timing': 'function', 'virtual': False, 'static': True,
        })
        if source['language'] == 'python':
            source['methods'].append({
                'canonical_id': source['canonical_id'] + '#wait_once', 'name': 'wait_once',
                'parameters': [], 'return_type': 'void', 'timing': 'task',
                'virtual': False, 'static': True,
            })
    return data
