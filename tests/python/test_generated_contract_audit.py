import copy

import pytest
import svtypes

from svx import inheritance, validate_generated_contracts
from svx.declarations import _type_declaration
from svx.errors import SVXInheritanceError


def test_normal_codec_materialization_does_not_compute_descriptor(monkeypatch):
    spec = _type_declaration(svtypes.Int, where='test')
    spec['encoding_descriptor']['encoding_fingerprint'] = '0'*64
    def forbidden(*args):
        pytest.fail('ordinary codec use must not calculate a diagnostic descriptor')
    monkeypatch.setattr(svtypes, 'encoding_descriptor', forbidden)
    assert isinstance(inheritance._svtypes_codec(spec), svtypes.Int)


def test_contract_audit_is_explicit_and_reports_affected_member(monkeypatch):
    spec = _type_declaration(svtypes.Int, where='test')
    monkeypatch.setattr(inheritance, '_method_contracts', {})
    monkeypatch.setattr(inheritance, '_constructor_contracts', {})
    changed = copy.deepcopy(spec)
    changed['encoding_descriptor']['encoding_fingerprint'] = '0'*64
    contract = {'parameters': (('value', 'input', changed),),
                'request': (('value', changed),), 'response': (), 'timing': 'function'}
    inheritance.register_contract({'sv://drivers/Driver#write': contract})
    with pytest.raises(SVXInheritanceError, match='drivers/Driver#write.value'):
        validate_generated_contracts()


def test_scalar_reference_validation_does_not_build_schema(monkeypatch):
    codec = svtypes.Int()
    def forbidden(*args):
        pytest.fail('a scalar without handles needs no reference schema traversal')
    monkeypatch.setattr(svtypes, 'schema_descriptor', forbidden)
    inheritance._validate_remote_refs(codec, 7)
