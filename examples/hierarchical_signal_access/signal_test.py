import svx
from svtypes import LogicValue

from .signal_declarations import data, ready, status


@svx.test
def test_signal_access():
    assert ready.read() == 0
    ready.write(1)
    svx.delay(1, "ns")
    assert ready.read() == 1

    data.write(0x3C)
    svx.delay(1, "ns")
    data.force(0xA5)
    svx.delay(1, "ns")
    assert data.read() == 0xA5
    data.release()
    data.write(0x3C)
    svx.delay(1, "ns")
    assert data.read() == 0x3C

    assert status.read() == LogicValue.from_string("10xz01z0")
    status.write(LogicValue.from_string("zx10xz01"))
    svx.delay(1, "ns")
    assert status.read() == LogicValue.from_string("zx10xz01")
    svx.display("hierarchical signal access example passed")
