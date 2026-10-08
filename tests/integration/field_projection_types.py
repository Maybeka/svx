"""Pure SvTypes factories used by the field-projection manifest."""

from svtypes import Array, AssocArray, Bit, Int, Object, ObjectRegistry, Queue, String, SvObject, svobj

_record_registry = ObjectRegistry()

@svobj(registry=_record_registry)
class DeepFieldRecord(SvObject):
    rows = AssocArray[String, Queue[Int]]()
    grid = Array[Bit[1], (2, 2)](cov=True)
    lanes = Array[Queue[Bit[1]], 2](cov=True)


def deep_record():
    return Object[DeepFieldRecord](registry=_record_registry)


def queue_of_int():
    return Queue[Int]()


def int_to_int():
    return AssocArray[Int, Int]()
