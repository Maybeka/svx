import svx
from svtypes import LogicValue

from .m14_signal_declarations import data, flag, logic_data


@svx.test
def test_signal_access():
    assert flag.read() == 0
    flag.write(1)
    svx.delay(1, "ns")
    assert flag.read() == 1

    data.write(0x3C)
    svx.delay(1, "ns")
    assert data.read() == 0x3C
    data.force(0xA5)
    svx.delay(1, "ns")
    assert data.read() == 0xA5
    data.release()
    data.write(0x3C)
    svx.delay(1, "ns")
    assert data.read() == 0x3C
    assert logic_data.read() == LogicValue.from_string("10xz01z0")
    logic_data.write(LogicValue.from_string("zx10xz01"))
    svx.delay(1, "ns")
    assert logic_data.read() == LogicValue.from_string("zx10xz01")
    svx.display("M14_SIGNAL_PASS")
