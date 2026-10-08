import json
from pathlib import Path, PurePosixPath
import sys

from svx.inheritance import _emit_sv_root_artifacts, _manifest_sv_record_types, artifact_manifest, parse_manifest
from svx.source_layout import _emit_sv_root_source_units
from tests.integration.same_package_schema import manifest_data as shared_manifest


def manifest_data():
    data = shared_manifest(shared_module=True)
    symbols = {'A': 'multi_a_pkg::A', 'C': 'multi_c_pkg::C', 'E': 'multi_e_pkg::E',
               'B': 'tests.integration.multi_unit_source.B', 'D': 'tests.integration.multi_unit_source.D'}

    def update(declaration):
        name = declaration['symbol'].rsplit('.', 1)[-1].rsplit('::', 1)[-1]
        declaration['symbol'] = symbols[name]
        for ancestor in declaration.get('base_lineage', []):
            update(ancestor)

    for declaration in data['classes']:
        update(declaration)
    data['classes'] = [data['classes'][-1]]
    return data


def source_inputs(*, diagnostic=False, configured=False):
    repo = Path(__file__).parents[2]
    return {str(path.relative_to(repo)): path.read_text() for name in (
        'multi_config_source.sv' if configured else 'multi_a_source.sv',
        'multi_diagnostic_consumer.sv' if diagnostic else 'multi_early_consumer.sv',
        'multi_c_source.sv', 'multi_e_source.sv')
        for path in (Path(__file__).with_name(name),)}


def emit_sources(*, diagnostic=False, configured=False):
    manifest = parse_manifest(manifest_data())
    common = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    common.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    common.append('endpackage')
    sv = {PurePosixPath('common.svh'): '\n'.join(common) + '\n',
          PurePosixPath('source.sv'): _emit_sv_root_source_units(manifest, source_inputs(diagnostic=diagnostic, configured=configured),
                                                               predefines={'SVX_MULTI_ENABLED': '1'} if configured else None)}
    return manifest, _emit_sv_root_artifacts(manifest, source_managed_layout=True), sv


if __name__ == '__main__':
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    diagnostic = '--diagnostic' in sys.argv[2:]
    manifest, python, sv = emit_sources(diagnostic=diagnostic, configured='--configured' in sys.argv[2:])
    for path, text in sv.items():
        (root / path).write_text(text)
    for path, text in python.items():
        output = root / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    (root / 'artifacts.json').write_text(json.dumps(artifact_manifest(
        manifest, python, python_path_prefix='python', sv_sources=sv), indent=2) + '\n')
    if diagnostic:
        (root / 'tb.sv').write_text(f'`include "sv/svx_pkg.sv"\n`include "{root}/common.svh"\n`include "{root}/source.sv"\n')
