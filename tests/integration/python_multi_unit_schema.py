import json
from pathlib import Path, PurePosixPath
import sys

from svx.inheritance import _emit_python_root_artifacts, _manifest_sv_record_types, artifact_manifest, parse_manifest
from svx.source_layout import _emit_python_root_source_units
from tests.integration.python_unit_schema import manifest_data as baseline


def manifest_data():
    data = baseline()
    final = data['classes'][0]
    final.update(canonical_id='sv://python_multi_final_pkg/Grandchild', symbol='python_multi_final_pkg::Grandchild')
    for method in final['methods']:
        method['canonical_id'] = final['canonical_id'] + '#' + method['name']
    return data


def source_inputs():
    repo = Path(__file__).parents[2]
    return {str(path.relative_to(repo)): path.read_text() for name in (
        'python_multi_child.sv', 'python_multi_consumer.sv', 'python_multi_final.sv')
        for path in (Path(__file__).with_name(name),)}


def emit_sources():
    manifest = parse_manifest(manifest_data())
    records = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    records.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    records.append('endpackage')
    sv = {PurePosixPath('common.svh'): '\n'.join(records) + '\n',
          PurePosixPath('source.sv'): _emit_python_root_source_units(manifest, source_inputs())}
    return manifest, _emit_python_root_artifacts(manifest, source_managed_layout=True), sv


if __name__ == '__main__':
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    manifest, python, sv = emit_sources()
    for path, text in sv.items():
        (root / path).write_text(text)
    for path, text in python.items():
        output = root / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    (root / 'artifacts.json').write_text(json.dumps(artifact_manifest(
        manifest, python, python_path_prefix='python', sv_sources=sv), indent=2) + '\n')
