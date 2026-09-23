import svx
from svx_mirrors.tb_pkg import BaseDriverMirror


class Driver(BaseDriverMirror):
    def __init__(self):
        super().__init__()

    def drive(self):
        super().drive()
        assert super().read_count() == 17
        svx.display("M9 Python super() returned from SV base")

    def read_count(self):
        return 19


@svx.export(name="m9.super_setup")
def setup():
    # Importing this module registers Driver as the Python implementation for
    # the SV-initiated BaseDriverMirror.  SV owns construction in this case.
    return None
