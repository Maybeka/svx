"""Internal staged SV-root target proof; public target integration is separate."""

import json
from pathlib import Path, PurePosixPath
import sys

from svx.inheritance import (
    _emit_sv_root_artifacts, _emit_sv_root_sv_packages, _manifest_sv_record_types,
    artifact_manifest, parse_manifest,
)
from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest


def manifest_data(*, extended=False, inherited_slot=False, branches=False, ordinary_middle=False, sv_prefix=False):
    data = field_manifest()
    binding = data['classes'][0]['fields'][0]['type']
    def method(owner, name, virtual=False):
        return {'canonical_id': owner + '#' + name, 'name': name, 'parameters': [],
                'return_type': binding, 'timing': 'function', 'virtual': virtual}
    a_id, b_id, c_id = 'sv://sv_root_pkg/A', 'py://tests/integration/sv_root/B', 'sv://sv_root_child_pkg/C'
    a = {'canonical_id': a_id, 'language': 'sv', 'symbol': 'sv_root_pkg::A',
         'constructor': {'initiator': 'python', 'parameters': []},
         'fields': [{'name': 'count', 'type': binding}], 'methods': [method(a_id, 'check', True)]}
    b = {'canonical_id': b_id, 'language': 'python', 'symbol': 'tests.integration.sv_root_target_test.B',
         'constructor': {'initiator': 'sv', 'parameters': []},
         'fields': [{'name': 'retry', 'type': binding}], 'methods': [method(b_id, 'check', True)]}
    c = {'canonical_id': c_id, 'language': 'sv', 'symbol': 'sv_root_child_pkg::C',
         'constructor': {'initiator': 'python', 'parameters': []},
         'fields': [{'name': 'extra', 'type': binding}],
         'methods': [method(c_id, 'check', True), method(c_id, 'observed_value')], 'base_lineage': [a, b]}
    data['classes'] = [c]
    if sv_prefix:
        z_id = 'sv://sv_root_prefix_pkg/Z'
        scale = method(z_id, 'prefix_scale')
        scale['static'] = True
        z = {'canonical_id': z_id, 'language': 'sv', 'symbol': 'sv_root_prefix_pkg::Z',
             'constructor': {'initiator': 'python', 'parameters': []},
             'fields': [{'name': 'prefix_count', 'type': binding}],
             'methods': [method(z_id, 'prefix_value'), method(z_id, 'prefix_virtual', True), scale]}
        c['base_lineage'].insert(0, z)
        b['methods'].append(method(b_id, 'prefix_virtual', True))
    if ordinary_middle:
        def static_method(owner, name):
            declaration = method(owner, name)
            declaration['static'] = True
            declaration['parameters'] = [{'name': 'value', 'type': binding}]
            return declaration
        middle_id = 'sv://sv_root_middle_pkg/Middle'
        a['methods'].append(static_method(a_id, 'root_scale'))
        wait = static_method(middle_id, 'middle_wait')
        wait.update(parameters=[], return_type='void', timing='task')
        middle = {'canonical_id': middle_id, 'language': 'sv', 'symbol': 'sv_root_middle_pkg::Middle',
                  'constructor': {'initiator': 'python', 'parameters': []},
                  'fields': [{'name': 'middle', 'type': binding}],
                  'methods': [method(middle_id, 'check', True), method(middle_id, 'middle_value'),
                              static_method(middle_id, 'middle_scale'), static_method(middle_id, 'scale'), wait]}
        c['base_lineage'].append(middle)
        c['methods'].append(static_method(c_id, 'scale'))
    if inherited_slot:
        c['methods'] = [method(c_id, 'observed_value')]
    if branches:
        b2_id, c2_id = 'py://tests/integration/sv_root/B2', 'sv://sv_root_branch_pkg/C2'
        b2 = {'canonical_id': b2_id, 'language': 'python',
              'symbol': 'tests.integration.sv_root_branch_test.B2',
              'constructor': {'initiator': 'sv', 'parameters': []},
              'fields': [{'name': 'retry', 'type': binding}],
              'methods': [method(b2_id, 'check', True)]}
        c2 = {'canonical_id': c2_id, 'language': 'sv', 'symbol': 'sv_root_branch_pkg::C2',
              'constructor': {'initiator': 'python', 'parameters': []},
              'fields': [{'name': 'extra', 'type': binding}],
              'methods': [method(c2_id, 'check', True), method(c2_id, 'observed_value')],
              'base_lineage': [*([z] if sv_prefix else []), a, b2]}
        data['classes'].append(c2)
    if extended:
        d_id, e_id = 'py://tests/integration/sv_root/D', 'sv://sv_root_e_pkg/E'
        c_decl = {key: value for key, value in c.items() if key != 'base_lineage'}
        d = {'canonical_id': d_id, 'language': 'python', 'symbol': 'tests.integration.sv_root_target_derived.D',
             'constructor': {'initiator': 'sv', 'parameters': []},
             'fields': [{'name': 'own', 'type': binding}], 'methods': [method(d_id, 'check', True)],
             'base_lineage': [*c['base_lineage'], c_decl]}
        d_decl = {key: value for key, value in d.items() if key != 'base_lineage'}
        e = {'canonical_id': e_id, 'language': 'sv', 'symbol': 'sv_root_e_pkg::E',
             'constructor': {'initiator': 'python', 'parameters': []},
             'fields': [{'name': 'e_value', 'type': binding}],
             'methods': [method(e_id, 'check', True), method(e_id, 'observed_python')],
             'base_lineage': [*c['base_lineage'], c_decl, d_decl]}
        data['classes'].extend([d, e])
    return data


def emit_sources(*, extended=False, inherited_slot=False, branches=False, ordinary_middle=False, sv_prefix=False):
    manifest = parse_manifest(manifest_data(extended=extended, inherited_slot=inherited_slot,
                                          branches=branches, ordinary_middle=ordinary_middle, sv_prefix=sv_prefix))
    common = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    for record in _manifest_sv_record_types(manifest):
        common.append(record.to_sv_obj(1))
    common.append('endpackage')
    sources = {PurePosixPath('common.svh'): '\n'.join(common) + '\n'}
    paths = {'svx_mirror_sv_sv_root_pkg_A': 'a.svh', 'svx_proxy_sv_root_target_test': 'b.svh',
             'svx_mirror_sv_sv_root_child_pkg_C': 'c.svh', 'svx_proxy_sv_root_target_derived': 'd.svh',
             'svx_mirror_sv_sv_root_e_pkg_E': 'e.svh', 'svx_proxy_sv_root_branch_test': 'b2.svh',
             'svx_mirror_sv_sv_root_branch_pkg_C2': 'c2.svh'}
    for package, text in _emit_sv_root_sv_packages(manifest, has_call_records=True).items():
        sources[PurePosixPath(paths[package])] = text
    python = _emit_sv_root_artifacts(manifest)
    return manifest, python, sources


if __name__ == '__main__':
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    manifest, python, sources = emit_sources(extended='--extended' in sys.argv[2:],
                                           inherited_slot='--inherited-slot' in sys.argv[2:],
                                           branches='--branches' in sys.argv[2:],
                                           ordinary_middle='--ordinary-middle' in sys.argv[2:],
                                           sv_prefix='--sv-prefix' in sys.argv[2:])
    for path, text in sources.items():
        (root / path).write_text(text)
    for path, text in python.items():
        output = root / 'python' / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    (root / 'artifacts.json').write_text(json.dumps(artifact_manifest(
        manifest, python, sv_sources=sources, python_path_prefix='python'), indent=2) + '\n')
