import svx
from svx_sv.tb_pkg import BaseDriver


class Driver(BaseDriver):
    def __init__(self):
        super().__init__(3)

    def drive(self):
        super().drive()
        assert super().read_count() == 17
        svx.display("M9 Python super() returned from SV base")

    def read_count(self):
        return 19


@svx.export(name="m9.super_setup")
def setup():
    Driver()
