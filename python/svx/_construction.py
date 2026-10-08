"""Internal typed, per-lineage constructor request protocol.

The staged generators still use single-portion requests. This contract is the
shared transport foundation for replacing that forwarding, not a public API.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import SVXInheritanceError
from .inheritance import (
    ForeignClass, _CallContract, _call_record_schema, _contract_schema, _decode_vif_view,
    _pack_call_record, _record_field, _record_value, _unpack_call_record,
    _validate_record_fields,
)


@dataclass(frozen=True)
class _ConstructorPortion:
    class_id: str
    contract: _CallContract


class _ConstructionRequest:
    """One ordered target plan, independent of parameter names in other stages."""

    def __init__(self, target: ForeignClass):
        from svtypes import Bit, Queue, String
        from .declarations import _svtypes_binding

        self.target_id = target.canonical_id
        lineage = (*target.base_lineage, target)
        if len({source.canonical_id for source in lineage}) != len(lineage):
            raise SVXInheritanceError('construction request contains duplicate lineage IDs')
        self.portions = tuple(_ConstructorPortion(source.canonical_id, _CallContract(
            (), tuple((parameter.name, parameter.type_binding.runtime_spec())
                      for parameter in (source.constructor.parameters if source.constructor else ())), (),
        )) for source in lineage)
        string = _svtypes_binding(String, where='construction target ID')
        octets = _svtypes_binding(Queue[Bit[8]], where='construction argument record')
        self.fields = (('target_id', string), *(
            field for index in range(len(self.portions))
            for field in ((f'owner_{index}', string), (f'arguments_{index}', octets))
        ))
        self.schema = _call_record_schema(self.target_id + '#construction', 'request', self.fields)

    def encode(self, arguments: Mapping[str, Mapping[str, Any]]) -> bytes:
        expected = {portion.class_id for portion in self.portions}
        if set(arguments) != expected:
            raise TypeError('construction arguments must identify every lineage class exactly once')
        values = {'target_id': self.target_id}
        for index, portion in enumerate(self.portions):
            supplied = dict(arguments[portion.class_id])
            schema = _contract_schema(portion.contract, portion.class_id, 'request')
            if schema is None:
                if supplied:
                    raise TypeError(f'constructor {portion.class_id} has no parameters')
                payload = b''
            else:
                payload = _pack_call_record(schema, _record_value(
                    schema, portion.contract.request_fields, supplied))
            values[f'owner_{index}'] = portion.class_id
            values[f'arguments_{index}'] = list(payload)
        return _pack_call_record(self.schema, _record_value(self.schema, self.fields, values))

    def decode(self, payload: bytes) -> dict[str, dict[str, Any]]:
        if not isinstance(payload, bytes):
            raise TypeError('construction request payload must be bytes')
        try:
            return self._decode(payload)
        except SVXInheritanceError:
            raise
        except Exception as error:
            raise SVXInheritanceError(f'invalid construction request for {self.target_id}: {error}') from error

    def _decode(self, payload: bytes) -> dict[str, dict[str, Any]]:
        value = _unpack_call_record(self.schema, payload)
        _validate_record_fields(value, self.fields)
        if _record_field(value, 'target_id') != self.target_id:
            raise SVXInheritanceError('construction request target differs from receiver plan')
        # Validate every identity before decoding any argument record/handle.
        for index, portion in enumerate(self.portions):
            if _record_field(value, f'owner_{index}') != portion.class_id:
                raise SVXInheritanceError('construction request lineage differs from receiver plan')
        result = {}
        for index, portion in enumerate(self.portions):
            record_payload = bytes(_record_field(value, f'arguments_{index}'))
            schema = _contract_schema(portion.contract, portion.class_id, 'request')
            if schema is None:
                if record_payload:
                    raise SVXInheritanceError(f'void constructor {portion.class_id} contains data')
                arguments = {}
            else:
                record = _unpack_call_record(schema, record_payload)
                _validate_record_fields(record, portion.contract.request_fields)
                arguments = {name: _decode_vif_view(_record_field(record, name))
                             for name, _ in portion.contract.request_fields}
            result[portion.class_id] = arguments
        return result

    def sv_record_types(self):
        """Public SvTypes schemas needed by the corresponding generated SV unit."""
        records = []
        for portion in self.portions:
            schema = _contract_schema(portion.contract, portion.class_id, 'request')
            if schema is not None:
                records.append(schema.value_type)
        records.append(self.schema.value_type)
        return tuple(records)
