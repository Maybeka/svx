from types import SimpleNamespace

import pytest
import svtypes

from svx.errors import SVXInheritanceError
from svx.struct_contract import CAPABILITY, struct_base
from svx.struct_contract import validate_struct_metadata


@pytest.mark.parametrize('packed', [None, 0, 1, 'true'])
def test_struct_requires_explicit_packing(packed):
    with pytest.raises(SVXInheritanceError, match='explicit boolean'):
        struct_base(packed, where='packet')


def test_struct_requires_advertised_capability(monkeypatch):
    monkeypatch.setattr(svtypes, 'runtime_capabilities', lambda: SimpleNamespace(provided=()))
    with pytest.raises(SVXInheritanceError, match=CAPABILITY):
        struct_base(False, where='packet')


@pytest.mark.parametrize('container', [
    {'kind': 'queue', 'args': [{'kind': 'struct', 'module': 'm', 'qualname': 'S'}]},
    {'kind': 'struct', 'packed': False, 'fields': [
        {'name': 'child', 'type': {'kind': 'struct'}}]},
])
def test_nested_struct_metadata_cannot_omit_packing(monkeypatch, container):
    monkeypatch.setattr(svtypes, 'runtime_capabilities',
                        lambda: SimpleNamespace(provided=(CAPABILITY,)))
    with pytest.raises(SVXInheritanceError, match='explicit boolean'):
        validate_struct_metadata(container, where='argument')


@pytest.mark.parametrize('packed', [False, True])
def test_struct_kind_selection_with_contract_fixture(monkeypatch, packed):
    monkeypatch.setattr(svtypes, 'runtime_capabilities',
                        lambda: SimpleNamespace(provided=(CAPABILITY,)))
    expected = getattr(svtypes, 'SvPackedStruct', None) if packed else svtypes.SvStruct
    if expected is None:
        pytest.skip('contract fixture requires new SvTypes public base')
    assert struct_base(packed, where='packet') is expected
