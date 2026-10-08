"""Qualify single-owner typed endpoints within their concrete source package."""

from pathlib import Path
import sys

from svx.inheritance import (_emit_sv_external_handle_adapters, _handle_adapter_name,
                             _manifest_handle_bindings, _manifest_sv_record_types, parse_manifest)
from tests.integration.constructor_handles_schema import manifest_data


def emit_sources():
    manifest = parse_manifest(manifest_data())
    bindings = _manifest_handle_bindings(manifest)
    records = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    records.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    records.append('endpackage')
    original = (Path(__file__).parent / 'constructor_handle_types.sv').read_text()
    owner = original.split('\npackage constructor_handle_pkg;', 1)[0].rstrip()
    owner = owner.removesuffix('endpackage')
    owner += '\n'.join(_emit_sv_external_handle_adapters(manifest, package_name=None))
    owner += '\nendpackage\npackage svx_external_handles_pkg;\n'
    for binding in bindings:
        name = _handle_adapter_name(binding)
        owner += f'  typedef external_handle_test_pkg::{name} {name};\n'
        owner += f'  typedef external_handle_test_pkg::{name}Endpoint {name}Endpoint;\n'
    owner += 'endpackage\n'
    return {'common.svh': '\n'.join(records) + '\n', 'source.sv': owner}


if __name__ == '__main__':
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    for name, text in emit_sources().items():
        (root / name).write_text(text)
