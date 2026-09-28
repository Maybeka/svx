import svx

from svx_mirror.example_driver_pkg import BaseDriver


class PythonDriver(BaseDriver):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def drive(self):
        self.calls += 1
        svx.display("PythonDriver received the SV virtual call")
        svx.delay(2, "ns")


@svx.export(name="inheritance.create_driver")
def create_driver():
    driver = PythonDriver()
    svx.publish_object("example.driver", driver)
