from svtypes import AssocArray, Int, Queue

import svx
from svx import inheritance_class
from svx_mirrors.field_pkg import BaseMirror
from tests.integration.field_projection_types import queue_of_int

released = False


@inheritance_class(
    canonical_id="py://tests/integration/field_projection/PythonLayer",
    constructor_initiator="sv",
)
class PythonLayer(BaseMirror):
    retry = Int()
    history = Queue(Int())
    mapping = AssocArray(Int(), Int())

    def __init__(self):
        super().__init__()
        self.retry.value = 7
        if self.retry.value != 7:
            raise AssertionError("projected SvTypes field did not round-trip during Python initialization")
        self.history.value.append(3)
        self.history.value.insert(0, 2)
        self.history.value[1] = 4
        if self.history.value.pop(0) != 2:
            raise AssertionError("projected SvTypes queue pop did not preserve the removed value")
        self.history.value.append(9)
        if list(self.history.value) != [4, 9]:
            raise AssertionError("projected SvTypes queue operations did not round-trip")
        self.mapping.value[1] = 6
        self.mapping.value[2] = 8
        del self.mapping.value[1]
        if dict(self.mapping.value) != {2: 8}:
            raise AssertionError("projected SvTypes associative updates did not round-trip")

    def _svx_release_projected_fields(self):
        global released
        super()._svx_release_projected_fields()
        released = True


@svx.export(name="field_projection.check_release")
def check_release():
    if not released:
        raise AssertionError("SV object release did not retire the Python projected-field binding")
