"""Keep native nested class identity without creating an enclosing object."""
import svx
from svtypes import Int, LogicValue
from svx_mirror_unit.unit_0 import Outer, OtherOuter, Outer_Inner, outer, UnitMode, UnitPacket, UnitModes


class PythonInner(Outer.Inner):
    def status(self):
        return super().status() + 100


@svx.export(name='unit_nested.run')
def run():
    driver = Outer.Inner(Int(10))
    assert driver.count.value == 10 and driver.status() == 11
    previous, total = svx.Output(), svx.Inout(5)
    driver.advance(Int(20), previous, total)
    assert previous.value == 10 and total.value == 25 and driver.count.value == 20
    assert Outer.Inner.twice(Int(3)) == 6
    assert driver.echo_mode(UnitMode.ACTIVE) == UnitMode.ACTIVE
    modes = UnitModes()
    modes.value = [UnitMode.IDLE, UnitMode.ACTIVE]
    assert driver.echo_modes(modes) == [UnitMode.IDLE, UnitMode.ACTIVE]
    packet = UnitPacket()
    packet.mode.value = UnitMode.ACTIVE
    packet.flags.value = LogicValue.from_string('10xz')
    echoed = driver.echo_packet(packet)
    assert echoed.mode.value == UnitMode.ACTIVE and echoed.flags.value == packet.flags.value
    driver.packet.value = packet
    driver.packet.flags.value = LogicValue.from_string('01zx')
    assert driver.packet.mode.value == UnitMode.ACTIVE
    assert driver.packet.flags.value == LogicValue.from_string('01zx')
    local_packet = Outer.Inner.Packet()
    local_packet.state.value = Outer.Inner.State.READY
    local_packet.flags.value = LogicValue.from_string('x01z')
    assert driver.echo_state(Outer.Inner.State.READY) == Outer.Inner.State.READY
    assert driver.echo_states([Outer.Inner.State.QUIET, Outer.Inner.State.READY]) == [0, 2]
    local_echo = driver.echo_local_packet(local_packet)
    assert local_echo.state.value == Outer.Inner.State.READY
    assert local_echo.flags.value == LogicValue.from_string('x01z')
    driver.local_packet.value = local_packet
    driver.local_packet.flags.value = LogicValue.from_string('z10x')
    assert driver.local_packet.state.value == Outer.Inner.State.READY
    assert driver.local_packet.flags.value == LogicValue.from_string('z10x')
    inherited = OtherOuter.Inner(Int(7))
    assert inherited.count.value == 8 and inherited.status() == 19
    assert OtherOuter.Inner.State is not Outer.Inner.State
    assert inherited.echo_state(Outer.Inner.State.READY) == Outer.Inner.State.READY
    assert inherited.echo_states([Outer.Inner.State.READY]) == [2]
    assert inherited.echo_local_state(OtherOuter.Inner.State.READY) == OtherOuter.Inner.State.READY
    inherited.local_packet.value = local_packet
    assert inherited.local_packet.state.value == Outer.Inner.State.READY
    alias = Outer.Alias(Int(4))
    assert alias.count.value == 4 and alias.status() == 5
    assert Outer_Inner(Int(3)).count.value == 23
    assert outer.Inner(Int(3)).count.value == 33
    assert Outer.Inner is not OtherOuter.Inner and Outer.Inner is not outer.Inner
    assert Outer.Inner.__qualname__ == 'Outer.Inner'
    child = PythonInner(Int(7))
    svx.publish_object('unit.nested', child)
    assert child.status() == 108
    svx.display('UNIT_NESTED_PYTHON_PASS')
