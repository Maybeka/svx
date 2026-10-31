"""Use an existing SV class without a handwritten manifest or declaration stub."""
import svx
from svtypes import Int, LogicValue
from svx_mirror.export_driver_pkg import Driver, Mode, Packet
from svx_mirror.export_base_pkg import Mode as BaseMode


class PythonDriver(Driver):
    def status(self):
        return super().status() + 100


@svx.export(name='sv_export.run')
def run():
    driver = Driver(Int(10))
    assert driver.status() == 11
    assert driver.count.value == 10
    previous, total = svx.Output(), svx.Inout(5)
    driver.advance(Int(20), previous, total)
    assert previous.value == 10 and total.value == 25
    assert driver.count.value == 20 and driver.status() == 21
    driver.count.value = 30
    assert driver.status() == 31
    assert Driver.twice(Int(3)) == 6
    assert driver.echo_mode(Mode.ACTIVE) == Mode.ACTIVE
    packet = Packet()
    packet.tag.value = 0xa5
    packet.flags.value = LogicValue.from_string('10xz')
    packet.mode.value = Mode.ACTIVE
    packet.base_mode.value = BaseMode.BASE_ACTIVE
    echoed = driver.echo_packet(packet)
    assert echoed.tag.value == 0xa5
    assert echoed.flags.value == LogicValue.from_string('10xz')
    assert echoed.mode.value == Mode.ACTIVE
    assert echoed.base_mode.value == BaseMode.BASE_ACTIVE
    assert driver.echo_base_mode(BaseMode.BASE_ACTIVE) == BaseMode.BASE_ACTIVE
    driver.packet.value = packet
    assert driver.packet.flags.value == LogicValue.from_string('10xz')
    driver.packet.tag.value = 0x5a
    assert driver.packet.tag.value == 0x5a
    assert driver.packet.flags.value == LogicValue.from_string('10xz')
    assert driver.packet.base_mode.value == BaseMode.BASE_ACTIVE
    child = PythonDriver(Int(7))
    assert child.status() == 108
    svx.publish_object('export.driver', child)
    svx.display('SV_EXPORT_PYTHON_PASS')
