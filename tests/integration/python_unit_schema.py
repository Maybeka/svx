import argparse
import json
from pathlib import Path, PurePosixPath

from svx.inheritance import _emit_python_root_artifacts, _manifest_sv_record_types, artifact_manifest, parse_manifest
from svx.source_layout import _emit_python_root_source_unit
from tests.integration.python_root_proxy_schema import probe_manifest_data


def manifest_data():
    data = probe_manifest_data()
    root, child, derived, final = (data['classes'][index] for index in (0, 2, 3, 4))
    for declaration, owner, symbol in (
        (root, 'py://tests/integration/python_unit/Root', 'tests.integration.python_unit_source.Root'),
        (child, 'sv://python_unit_pkg/Child', 'python_unit_pkg::Child'),
        (derived, 'py://tests/integration/python_unit/Derived', 'tests.integration.python_unit_source.Derived'),
        (final, 'sv://python_unit_pkg/Grandchild', 'python_unit_pkg::Grandchild'),
    ):
        declaration.update(canonical_id=owner, symbol=symbol)
        for method in declaration['methods']:
            method['canonical_id'] = owner + '#' + method['name']
    child['base_lineage'] = [root]
    derived['base_lineage'] = [root, {key: value for key, value in child.items() if key != 'base_lineage'}]
    final['base_lineage'] = [*derived['base_lineage'], {key: value for key, value in derived.items() if key != 'base_lineage'}]
    data['classes'] = [final]
    return data


def emit_sources(*, base_macros=False):
    manifest = parse_manifest(manifest_data())
    records = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    records.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    records.append('endpackage')
    source = Path(__file__).with_name('python_unit_source.sv').read_text()
    if base_macros:
        source = ('`define UNIT_PROXY(MEMBER) svx_proxy_python_unit_source::MEMBER\n' + source.replace(
            'extends svx_proxy_python_unit_source::Root;', 'extends `UNIT_PROXY(Root);').replace(
            'extends svx_proxy_python_unit_source::Derived;', 'extends `UNIT_PROXY(Derived);'))
    sv = {PurePosixPath('common.svh'): '\n'.join(records) + '\n',
          PurePosixPath('source.sv'): _emit_python_root_source_unit(manifest, source)}
    return manifest, _emit_python_root_artifacts(manifest, source_managed_layout=True), sv


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--base-macros', action='store_true')
    args = parser.parse_args()
    root = args.out
    root.mkdir(parents=True, exist_ok=True)
    manifest, python, sv = emit_sources(base_macros=args.base_macros)
    for path, text in sv.items():
        (root / path).write_text(text)
    for path, text in python.items():
        output = root / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    (root / 'artifacts.json').write_text(json.dumps(artifact_manifest(
        manifest, python, python_path_prefix='python', sv_sources=sv), indent=2) + '\n')
