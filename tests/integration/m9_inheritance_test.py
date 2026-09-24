import svx
from svx_mirrors.tb_pkg import (
    BaseDriverCalculateResponse,
    BaseDriverDriveResponse,
    BaseDriverMirror,
)


class PythonDriver(BaseDriverMirror):
    def __init__(self, seed):
        if seed != 9:
            raise AssertionError(f"expected factory seed 9, got {seed}")

    def drive(self, address, changed, label, packet):
        if address != 37:
            raise AssertionError(f"expected address 37, got {address}")
        if label != "factory-driver":
            raise AssertionError(f"expected factory-driver, got {label}")
        if packet.address.value != 37 or packet.label.value != "object-payload":
            raise AssertionError("SvTypes object payload did not round-trip")
        if self.base_value() != 91:
            raise AssertionError("Python non-virtual override did not use normal Python lookup")
        if BaseDriverMirror.base_value(self) != 18:
            raise AssertionError("non-virtual SV base call did not reach BaseDriver")
        if self.static_value() != 91:
            raise AssertionError("Python static override did not use normal Python lookup")
        if BaseDriverMirror.static_value() != 71:
            raise AssertionError("static SV base call did not reach BaseDriver")
        svx.display("M10 Python integral argument decoded")
        svx.delay(2, "ns")
        return BaseDriverDriveResponse(changed=changed + 1, observed=address + 20)

    def calculate(self, source, changed):
        return BaseDriverCalculateResponse(
            changed=changed + source,
            observed=changed + source + 30,
            result=changed + source + 31,
        )

    def base_value(self):
        return 91

    @staticmethod
    def static_value():
        return 91


@svx.export(name="m9.setup")
def setup():
    svx._native.inheritance_stats_reset()


@svx.export(name="m9.report")
def report():
    count, nanoseconds = svx._native.inheritance_stats()
    if count != 11:
        raise AssertionError(f"expected 11 callbacks, got {count}")
    svx.display(f"M13 inheritance callback baseline: {nanoseconds / count:.0f} ns/call")
