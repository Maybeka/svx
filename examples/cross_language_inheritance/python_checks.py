import svx

from svx_sv.example_driver_pkg import BaseDriver


class PythonDriver(BaseDriver):
    def __init__(self, seed):
        assert seed == 9, f"expected seed 9, got {seed}"

    def drive(self, address):
        assert address == 0x40, f"expected address 0x40, got 0x{address:x}"
        svx.display("PythonDriver received the SV virtual call")
        svx.delay(2, "ns")


@svx.export(name="inheritance.report")
def report():
    svx.display("cross-language inheritance example passed")
