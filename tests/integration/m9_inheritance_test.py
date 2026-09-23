import svx
from svx_mirrors.tb_pkg import BaseDriverMirror


class PythonDriver(BaseDriverMirror):
    def __init__(self, seed):
        if seed != 9:
            raise AssertionError(f"expected factory seed 9, got {seed}")

    def drive(self, address, label, packet):
        if address != 37:
            raise AssertionError(f"expected address 37, got {address}")
        if label != "factory-driver":
            raise AssertionError(f"expected factory-driver, got {label}")
        if packet.address.value != 37 or packet.label.value != "object-payload":
            raise AssertionError("SvTypes object payload did not round-trip")
        svx.display("M10 Python integral argument decoded")
        svx.delay(2, "ns")


@svx.export(name="m9.setup")
def setup():
    svx._native.inheritance_stats_reset()


@svx.export(name="m9.report")
def report():
    count, nanoseconds = svx._native.inheritance_stats()
    if count != 10:
        raise AssertionError(f"expected 10 measured callbacks, got {count}")
    svx.display(f"M13 inheritance callback baseline: {nanoseconds / count:.0f} ns/call")
