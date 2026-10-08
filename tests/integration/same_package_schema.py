"""Internal parsed source-unit proof for a same-package SV-root lineage."""

import json
from pathlib import Path, PurePosixPath
import sys

from svx.inheritance import (
    _emit_sv_root_artifacts, _manifest_sv_record_types, artifact_manifest, parse_manifest,
)
from svx.source_layout import _emit_sv_root_source_unit
from tests.integration.sv_root_target_schema import manifest_data as baseline


def manifest_data(*, shared_module=False):
    data = baseline(extended=shared_module)
    target = data['classes'][0]
    a, b = target['base_lineage']
    for declaration, owner, symbol in (
        (a, 'sv://same_package_pkg/A', 'same_package_pkg::A'),
        (b, 'py://tests/integration/same_package/B', 'tests.integration.' + ('same_module_source' if shared_module else 'same_package_test') + '.B'),
        (target, 'sv://same_package_pkg/C', 'same_package_pkg::C'),
    ):
        declaration.update(canonical_id=owner, symbol=symbol)
        for method in declaration['methods']:
            method['canonical_id'] = owner + '#' + method['name']
    scale = dict(a['methods'][0], canonical_id=a['canonical_id'] + '#scale', name='scale',
                 virtual=False, static=True)
    a['methods'].append(scale)
    if shared_module:
        d, e = data['classes'][1:]
        for declaration, owner, symbol in (
            (d, 'py://tests/integration/same_package/D', 'tests.integration.same_module_source.D'),
            (e, 'sv://same_package_pkg/E', 'same_package_pkg::E'),
        ):
            declaration.update(canonical_id=owner, symbol=symbol)
            for method in declaration['methods']:
                method['canonical_id'] = owner + '#' + method['name']
        d['base_lineage'] = [a, b, {key: value for key, value in target.items() if key != 'base_lineage'}]
        e['base_lineage'] = [*d['base_lineage'], {key: value for key, value in d.items() if key != 'base_lineage'}]
    return data


def emit_sources(source=None, *, shared_module=False):
    manifest = parse_manifest(manifest_data(shared_module=shared_module))
    if source is None:
        source = Path(__file__).with_name('same_module_source.sv' if shared_module else 'same_package_source.sv').read_text()
    common = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    common.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    common.append('endpackage')
    sv = {PurePosixPath('common.svh'): '\n'.join(common) + '\n',
          PurePosixPath('source.sv'): _emit_sv_root_source_unit(manifest, source)}
    python = _emit_sv_root_artifacts(manifest, source_managed_layout=True)
    return manifest, python, sv


if __name__ == '__main__':
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    manifest, python, sources = emit_sources(shared_module='--shared-module' in sys.argv[2:])
    for path, text in sources.items():
        (root / path).write_text(text)
    for path, text in python.items():
        output = root / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources=sources)
    (root / 'artifacts.json').write_text(json.dumps(metadata, indent=2) + '\n')
