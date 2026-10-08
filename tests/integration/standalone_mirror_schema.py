"""SV-origin standalone mirror with methods but no projected fields."""

import json
from pathlib import Path
import sys

from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def manifest_data(*, include_fields=False):
    data = field_manifest()
    data['classes'] = data['classes'][:1]
    if not include_fields:
        data['classes'][0]['fields'] = []
    data['classes'][0]['constructor']['initiator'] = 'sv'
    return data


if __name__ == '__main__':
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest_data(include_fields='--fields' in sys.argv[2:]), indent=2) + '\n')
