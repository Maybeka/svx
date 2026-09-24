import pytest

from svtypes import Int, Queue, SvObject, svobj

from svx import SVXInheritanceError
from svx.field_storage import (
    SVXFieldStorage,
    bind_projected_fields,
    projected_field_identities,
)


@svobj
class FieldOwner(SvObject):
    count = Int()
    local = Int()
    history = Queue(Int())


class RecordingTransport:
    def __init__(self) -> None:
        self.values = {"py://checks/B.count": Int().pack(3)}
        self.reads = []
        self.writes = []

    def read_field(self, object_id, field_id, descriptor, path):
        self.reads.append((object_id, field_id, descriptor, path))
        return self.values[field_id]

    def write_field(self, object_id, field_id, descriptor, path, operation, payload):
        self.writes.append((object_id, field_id, descriptor, path, operation, payload))
        self.values[field_id] = payload
        return None


def test_selected_svtypes_fields_bind_to_svx_object_storage():
    owner = FieldOwner()
    transport = RecordingTransport()
    ids = projected_field_identities(owner, {"count": "py://checks/B.count"})
    storage = SVXFieldStorage(transport)
    bind_projected_fields(owner, 91, ids, storage=storage)

    assert owner.count.value == 3
    owner.count.value = 9
    assert owner.count.value == 9
    assert transport.reads[0][0:2] == (91, "py://checks/B.count")
    assert transport.reads[0][3] == "[]"
    assert transport.writes[-1][0:2] == (91, "py://checks/B.count")
    assert transport.writes[-1][4] == "set"
    # An omitted field remains a normal owner-local SvTypes value.
    owner.local.value = 4
    assert owner.local.value == 4


def test_projected_field_identity_rejects_unknown_or_shadowed_names():
    owner = FieldOwner()
    with pytest.raises(SVXInheritanceError, match="no unique declaring class"):
        projected_field_identities(owner, {"missing": "py://checks/B.missing"})


def test_projected_queue_keeps_svtypes_local_operation_paths():
    owner = FieldOwner()
    transport = RecordingTransport()
    ids = projected_field_identities(owner, {"history": "py://checks/B.history"})
    bind_projected_fields(owner, 91, ids, storage=SVXFieldStorage(transport))

    owner.history.value.append(3)
    owner.history.value.insert(0, 2)
    owner.history.value[0] = 4

    assert [(write[3], write[4]) for write in transport.writes] == [
        ("[]", "append"),
        ('[{"kind":"index","index":0}]', "insert"),
        ('[{"kind":"index","index":0}]', "set"),
    ]
