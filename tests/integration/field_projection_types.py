"""Pure SvTypes factories used by the field-projection manifest."""

from svtypes import AssocArray, Int, Queue


def queue_of_int():
    return Queue(Int())


def int_to_int():
    return AssocArray(Int(), Int())
