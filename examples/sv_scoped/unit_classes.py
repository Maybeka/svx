"""Construct and extend a native compilation-unit class from Python."""
import svx
from svtypes import Int
from svx_mirror_unit.unit_0 import Driver
from svx_mirror.unit_base_pkg import Mode


class PythonDriver(Driver):
    def status(self):
        return super().status() + 100


@svx.export(name='unit_classes.run')
def run():
    driver = Driver(Int(10))
    assert driver.count.value == 10 and driver.inherited.value == 11
    assert driver.status() == 11
    previous, total = svx.Output(), svx.Inout(5)
    driver.advance(Int(20), previous, total)
    assert previous.value == 10 and total.value == 25
    assert driver.count.value == 20 and driver.inherited.value == 11
    driver.count.value = 30
    driver.inherited.value = 40
    assert driver.status() == 31 and Driver.twice(Int(3)) == 6
    assert Driver.inherited_twice(Int(4)) == 8
    assert Driver.local_twice(Int(5)) == 10
    assert driver.echo_mode(Mode.ACTIVE) == Mode.ACTIVE
    child = PythonDriver(Int(7))
    assert child.status() == 108 and child.inherited.value == 8
    svx.publish_object('unit.driver', child)
    svx.display('UNIT_CLASSES_PYTHON_PASS')
