"""Qualify planned root packages without hand-written private helper names."""

import json
from pathlib import Path, PurePosixPath
import sys

from svx.inheritance import (
    _emit_python_root_artifacts, _emit_python_root_sv_packages,
    _manifest_sv_record_types, artifact_manifest, parse_manifest,
)
from tests.integration.python_root_proxy_schema import probe_manifest_data


def manifest_data(*, sv_origin_only=False):
    data = probe_manifest_data()
    data['classes'] = data['classes'][:5]
    target = data['classes'][4]
    old_id = target['canonical_id']
    target['canonical_id'] = 'sv://python_root_e_probe_pkg/Grandchild'
    target['symbol'] = 'python_root_e_probe_pkg::Grandchild'
    for method in target['methods']:
        method['canonical_id'] = method['canonical_id'].replace(old_id, target['canonical_id'])
    if sv_origin_only:
        target['constructor']['initiator'] = 'sv'
    return data


def emit_sources(*, sv_origin_only=False):
    model = parse_manifest(manifest_data(sv_origin_only=sv_origin_only))
    records = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    for record in _manifest_sv_record_types(model):
        records.append(record.to_sv_obj(1))
    records.extend(['endpackage', ''])
    sources = {PurePosixPath('common.svh'): '\n'.join(records)}
    for package, text in _emit_python_root_sv_packages(model, has_call_records=True).items():
        sources[PurePosixPath(package + '.svh')] = text
    return model, _emit_python_root_artifacts(model), sources


if __name__ == '__main__':
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    model, python, sources = emit_sources(sv_origin_only='--sv-origin-only' in sys.argv[2:])
    for path, source in sources.items():
        (root / path).write_text(source)
    for path, source in python.items():
        output = root / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source)
    metadata = artifact_manifest(model, python, sv_sources=sources, python_path_prefix='python')
    (root / 'artifacts.json').write_text(json.dumps(metadata, indent=2) + '\n')
