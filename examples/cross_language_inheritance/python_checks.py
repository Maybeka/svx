import svx

from svx_mirrors.example_driver_pkg import BaseDriverMirror


class PythonDriver(BaseDriverMirror):
    def drive(self):
        svx.display("PythonDriver received the SV virtual call")
        svx.delay(2, "ns")


@svx.export(name="inheritance.report")
def report():
    svx.display("cross-language inheritance example passed")
