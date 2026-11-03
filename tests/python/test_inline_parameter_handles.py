from pathlib import Path

import pytest

from svx.declarations import manifest_from_declarations
from svx.inheritance import emit_sv_mirrors

pytest.importorskip('pyslang')
SOURCE = Path(__file__).parents[1] / 'integration/inline_parameter_handles.sv'


@pytest.mark.parametrize('package', [False, True])
def test_inline_parameter_handles_and_imported_class_enum(package):
    selectors = {'sv_package_targets': ['inline_drivers_pkg']} if package else {'sv_class_targets': ['inline_drivers_pkg::Driver']}
    manifest = manifest_from_declarations(sv_source_files=[SOURCE],
        sv_exclude_members=['inline_drivers_pkg::Base.excluded_noise'], **selectors)
    driver = next(item for item in manifest.classes if item.name == 'Driver')
    methods = {method.name: method for method in driver.methods}
    default = methods['default_tag'].parameters[0].handle
    wide = methods['wide_tag'].parameters[0].handle
    typed = methods['typed_value'].parameters[0].handle
    assert default.target_type_name != wide.target_type_name
    assert default.target_type_name == 'sv://inline_types_pkg/Packet'
    assert default == methods['make_default'].return_handle
    assert default == methods['explicit_default_tag'].parameters[0].handle
    assert wide == methods['make_wide'].return_handle == methods['echo'].return_handle
    assert typed == methods['make_typed'].return_handle
    assert wide.sv_type == 'inline_types_pkg::Packet#(16)'
    assert 'inline_types_pkg::Typed#(' in typed.sv_type
    nested = methods['nested_value'].parameters[0].handle
    assert nested == methods['make_nested'].return_handle
    assert nested.sv_type == 'inline_types_pkg::Typed#(inline_types_pkg::Packet#(16))'
    assert methods['echo_mode'].parameters[0].type_binding == methods['echo_mode'].return_type
    assert 'inline_types_pkg::Packet#(16)' in emit_sv_mirrors(manifest)


@pytest.mark.parametrize('parameter,argument', [
    ('int N = 8', '-1'), ('string NAME = "default"', '"hello"'),
    ('int N', '16'),
])
def test_closed_handle_parameter_literals(tmp_path, parameter, argument):
    path = tmp_path / 'literal.sv'
    path.write_text(f'package p; class P#({parameter}); endclass '
                    f'class D; function P#({argument}) echo(P#({argument}) item); return item; endfunction '
                    'endclass endpackage\n', encoding='utf-8')
    manifest = manifest_from_declarations(sv_source_files=[path], sv_class_targets=['p::D'])
    method = manifest.classes[0].methods[0]
    assert method.return_handle == method.parameters[0].handle
    assert f'p::P#({argument})' in emit_sv_mirrors(manifest)
