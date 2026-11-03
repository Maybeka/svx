from types import SimpleNamespace

import pytest

from svx.errors import SVXInheritanceError
from svx.field_kernels import field_kernel


def test_field_kernel_keeps_index_paths_and_binds_original_variable_by_ref():
    cases = ['        "field@read": begin',
             '          codec::pack(this.values[operation.path_index[0]].tag, bytes);',
             '          this.values[0].tag = 7;', '        end']
    core, dispatch = field_kernel(SimpleNamespace(name='values'), cases, 'svx_core_field_values')
    text = '\n'.join(core)
    assert 'ref SVXResidentType __svx_resident_value' in text
    assert '__svx_resident_value[operation.path_index[0]].tag' in text
    assert '__svx_resident_value[0].tag = 7;' in text
    assert '#(type(this.values))::invoke(this.values,' in text
    assert 'this.svx_core_field_values(method_id, bytes, ok, response, error);' in '\n'.join(dispatch)


def test_field_kernel_rejects_hidden_owner_dependencies():
    with pytest.raises(SVXInheritanceError, match='unexpectedly accesses owner member other'):
        field_kernel(SimpleNamespace(name='values'),
                     ['        "field@read": begin', '          this.other = 7;', '        end'],
                     'svx_core_field_values')
