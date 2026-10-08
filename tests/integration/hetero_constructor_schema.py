import json
from pathlib import Path, PurePosixPath
import sys

from svtypes import String
from svx.declarations import _svtypes_binding
from svx.inheritance import _emit_python_root_artifacts, _manifest_sv_record_types, artifact_manifest, parse_manifest
from svx.source_layout import _emit_python_root_source_units
from tests.integration.python_unit_schema import manifest_data as baseline


def manifest_data():
    data = baseline()
    final = data['classes'][0]
    root, child, derived = final['base_lineage']
    count = root['fields'][0]['type']
    count.pop('svtypes', None)
    count['python'] = {'module': 'tests.integration.hetero_constructor_defaults',
                       'symbol': 'count_codec', 'args': [], 'kwargs': {}}
    for source, symbol in (
        (root, 'tests.integration.hetero_constructor_source.Root'),
        (child, 'hetero_child_pkg::Child'),
        (derived, 'tests.integration.hetero_constructor_source.Derived'),
        (final, 'hetero_final_pkg::Grandchild'),
    ):
        source['symbol'] = symbol
    label = {'name': 'label', 'type': _svtypes_binding(String, where='constructor label')}
    child['constructor']['parameters'].append(label)
    derived['constructor']['parameters'].append(dict(label))
    final['constructor']['parameters'] = []
    return data


def emit_sources():
    manifest = parse_manifest(manifest_data())
    records = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    records.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    records.append('endpackage')
    source = Path(__file__).with_name('hetero_constructor_source.sv')
    sv = {PurePosixPath('common.svh'): '\n'.join(records) + '\n',
          PurePosixPath('source.sv'): _emit_python_root_source_units(manifest, {
              'tests/integration/hetero_constructor_source.sv': source.read_text()})}
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
