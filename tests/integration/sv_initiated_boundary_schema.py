"""Public-generator regression for an explicitly SV-owned boundary constructor."""

import json
from pathlib import Path
import sys

from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def manifest_data():
    data = field_manifest(include_four_state=True)
    data['classes'][0]['constructor']['initiator'] = 'sv'
    data['classes'][1]['canonical_id'] = 'py://tests/integration/sv_initiated_boundary/Derived'
    data['classes'][1]['symbol'] = 'tests.integration.sv_initiated_boundary_test.Derived'
    return data


if __name__ == '__main__':
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest_data(), indent=2) + '\n')
