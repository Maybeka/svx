import io
import re
from pathlib import Path

import pytest

from svx.cli import main


pytest.importorskip('pyslang')


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('integrated', [False, True])
def test_export_type_reference_option(tmp_path, enabled, integrated):
    source = tmp_path / 'source.sv'
    source.write_text('package p; class Driver; int value; endclass endpackage\n', encoding='utf-8')
    output = tmp_path / 'generated'
    arguments = ['export', '--package', 'p', '--sv-source', str(source), '--out', str(output)]
    if integrated:
        arguments.append('--integrated')
    if enabled:
        arguments.append('--use-type-reference')
    assert main(arguments, out=io.StringIO()) == 0
    sv = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*')
                   if path.suffix in {'.sv', '.svh'})
    assert bool(re.search(r'\btype\s*\(', sv)) is enabled
    assert main([*arguments, '--check'], out=io.StringIO()) == 0


def test_svtypes_gen_type_reference_option():
    base = ['svtypes-gen', '--module', 'examples.register_lab.models']
    plain = io.StringIO()
    enabled = io.StringIO()
    assert main(base, out=plain) == 0
    assert main([*base, '--use-type-reference'], out=enabled) == 0
    assert not re.search(r'\btype\s*\(', plain.getvalue())
    assert re.search(r'\btype\s*\(', enabled.getvalue())


@pytest.mark.parametrize('enabled', [False, True])
def test_inheritance_gen_type_reference_option(tmp_path, enabled):
    source = tmp_path / 'source.sv'
    source.write_text('package p; class Driver; int value; endclass endpackage\n', encoding='utf-8')
    discovered = tmp_path / 'manifest.json'
    assert main(['inheritance-manifest', '--class', 'p::Driver', '--sv-source', str(source),
                 '--out', str(discovered)], out=io.StringIO()) == 0
    sv = tmp_path / 'mirrors.sv'
    args = ['inheritance-gen', '--manifest', str(discovered), '--sv-out', str(sv)]
    if enabled:
        args.append('--use-type-reference')
    assert main(args, out=io.StringIO()) == 0
    assert bool(re.search(r'\btype\s*\(', sv.read_text(encoding='utf-8'))) is enabled


def test_nested_reference_typedefs_keep_native_and_wire_types_distinct():
    from svx.struct_contract import _reference_schema_typedefs

    schema = {'kind': 'queue', 'element': {'kind': 'queue', 'element': {
        'kind': 'remote_ref', 'target_type_name': 'sv://items/Item'}}}
    native = '\n'.join(_reference_schema_typedefs(schema, 'nested', native=True))
    wire = '\n'.join(_reference_schema_typedefs(schema, 'nested', native=False))
    assert 'typedef items::Item nested_element_element;' in native
    assert 'typedef svtypes_pkg::remote_ref nested_element_element;' in wire
    assert 'typedef nested_element nested[$];' in native and 'type(' not in native


@pytest.mark.parametrize('enabled', [False, True])
def test_nested_handle_struct_exports_in_both_modes(tmp_path, enabled):
    source = Path(__file__).parents[1] / 'integration/nested_struct_ref.sv'
    output = tmp_path / 'generated'
    args = ['export', '--package', 'nested_struct_ref_pkg', '--sv-source', str(source), '--out', str(output)]
    if enabled:
        args.append('--use-type-reference')
    assert main(args, out=io.StringIO()) == 0
    sv = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*')
                   if path.suffix in {'.sv', '.svh'})
    assert bool(re.search(r'\btype\s*\(', sv)) is enabled


def test_type_reference_variable_declarations_use_var(tmp_path):
    source = Path(__file__).parents[1] / 'integration/struct_kinds.sv'
    output = tmp_path / 'generated'
    assert main(['export', '--package', 'struct_kinds_pkg', '--sv-source', str(source),
                 '--out', str(output), '--use-type-reference'], out=io.StringIO()) == 0
    sv = '\n'.join(path.read_text(encoding='utf-8') for path in output.rglob('*')
                   if path.suffix in {'.sv', '.svh'})
    assert re.search(r'\bvar\s+type\s*\(', sv)
    assert not re.search(r'(?m)^\s*type\s*\([^\n]+\)\s+\w+\s*;', sv)
