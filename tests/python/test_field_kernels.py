from types import SimpleNamespace

import pytest

from svx.errors import SVXInheritanceError
from svx.field_kernels import field_kernel
from svx.sv_codegen_mode import type_reference_mode


def test_field_kernel_keeps_index_paths_and_binds_original_variable_by_ref():
    cases = ['        "field@read": begin',
             '          codec::pack(this.values[operation.path_index[0]].tag, bytes);',
             '          this.values[0].tag = 7;', '        end']
    with type_reference_mode(True):
        core, dispatch = field_kernel(SimpleNamespace(name='values'), cases, '_svx__core_field_values')
    text = '\n'.join(core)
    assert 'ref SVXResidentType __svx_resident_value' in text
    assert '__svx_resident_value[operation.path_index[0]].tag' in text
    assert '__svx_resident_value[0].tag = 7;' in text
    assert '#(type(this.values))::invoke(this.values,' in text
    assert 'this._svx__core_field_values(method_id, bytes, ok, response, error);' in '\n'.join(dispatch)


def test_default_field_binding_uses_original_member_without_type_reference():
    cases = ['        "field@read": begin', '          this.values[0] = 7;', '        end']
    core, _ = field_kernel(SimpleNamespace(name='values'), cases, '_svx__core_field_values')
    text = '\n'.join(core)
    assert 'this.values[0] = 7;' in text
    assert 'type(' not in text


def test_field_kernel_rejects_hidden_owner_dependencies():
    with pytest.raises(SVXInheritanceError, match='unexpectedly accesses owner member other'):
        field_kernel(SimpleNamespace(name='values'),
                     ['        "field@read": begin', '          this.other = 7;', '        end'],
                     '_svx__core_field_values')
