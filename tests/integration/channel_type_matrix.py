import svx
from svtypes import (
    Array, AssocArray, Bit, DynArray, Enum, Int, Logic, LogicValue,
    Object, Queue, Real, RemoteRef, RemoteRefValue, String,
    SvObject, get_package, svobj,
)

registry = get_package("svx_channel_type_matrix")


class MatrixMode(Enum[Bit[8]]):
    MATRIX_FIRST = 1
    MATRIX_SECOND = 2


@svobj(registry=registry)
class MatrixNode(SvObject):
    number = Int(rand=False, cov=False)
    link = Object["MatrixNode"](registry=registry)


@svobj(registry=registry)
class MatrixValue(SvObject):
    packed_value = Bit[13](rand=False, cov=False)
    four_state = Logic[9](rand=False, cov=False)
    mode = MatrixMode(rand=False, cov=False)
    text = String(rand=False, cov=False)
    real_value = Real(rand=False, cov=False)
    fixed = Array[Int, 3](rand=False, cov=False)
    dynamic = DynArray[Int](rand=False, cov=False)
    queue_value = Queue[Int](rand=False, cov=False)
    nested = Queue[Queue[Int]](rand=False, cov=False)
    lookup = AssocArray[String, Int](rand=False, cov=False)
    first = Object["MatrixNode"](registry=registry)
    shared_node = Object["MatrixNode"](registry=registry)
    reference = RemoteRef["sv://matrix/Opaque"](rand=False, cov=False)


def make_value(index: int) -> MatrixValue:
    value = MatrixValue()
    value.packed_value.value = 0x1234
    value.four_state.value = LogicValue(9, 0x15, 0x40, 0x100)
    value.mode.value = MatrixMode.MATRIX_SECOND
    value.text.value = f"iteration-{index}"
    value.real_value.value = 1.25
    value.fixed.value = [1, -2, 3]
    value.dynamic.value = [index, -7]
    value.queue_value.value = [8, 9]
    value.nested.value = [[1, 2], [3]]
    value.lookup.value = {"beta": -4, "alpha": 17}
    if index:
        node = MatrixNode()
        node.number.value = index
        node.link = node
        value.first = node
        value.shared_node = node
    else:
        value.first = None
        value.shared_node = None
    value.reference.value = RemoteRefValue("sv://matrix/Opaque", 0)
    return value


def verify_value(value: MatrixValue, index: int) -> None:
    assert value.packed_value.value == 0x1234
    assert value.four_state.value == LogicValue(9, 0x15, 0x40, 0x100)
    assert value.mode.value == MatrixMode.MATRIX_SECOND
    assert value.text.value == f"iteration-{index}"
    assert value.real_value.value == 1.25
    assert value.fixed.value == [1, -2, 3]
    assert value.dynamic.value == [index, -7]
    assert value.queue_value.value == [8, 9]
    assert value.nested.value == [[1, 2], [3]]
    assert value.lookup.value == {"alpha": 17, "beta": -4}
    if index:
        node = value.first
        assert node is value.shared_node
        assert node.link is node
        assert node.number.value == index
    else:
        assert value.first is None and value.shared_node is None
    assert value.reference.value == RemoteRefValue("sv://matrix/Opaque", 0)


@svx.export(name="channel_matrix.run")
def run() -> None:
    for index in range(3):
        svx.channel("matrix.req").put(make_value(index))
        verify_value(svx.channel("matrix.rsp").get(MatrixValue), index)
    svx.display("SVX_CHANNEL_TYPE_MATRIX_PASS")
