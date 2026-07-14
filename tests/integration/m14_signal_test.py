import svx

from .m14_signal_declarations import data, flag


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
    svx.display("M14_SIGNAL_PASS")
