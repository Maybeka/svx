"""Use scoped native types without creating their lexical owner objects."""
import svx
from svtypes import Int, LogicValue
from svx_mirror.scoped_classes_pkg import Outer, OtherOuter, outer, Outer_Inner, Mode, Packet


class PythonInner(Outer.Inner):
    def status(self):
        return super().status()+100


@svx.export(name='sv_scoped.run')
def run():
    assert Outer.Inner.__name__ == OtherOuter.Inner.__name__ == 'Inner'
    assert Outer.Inner.__module__ == 'svx_mirror.scoped_classes_pkg'
    assert Outer.Inner.__qualname__ == 'Outer.Inner'
    first = Outer.Inner(Int(3))
    assert first.count.value == 4 and first.status() == 14
    first.count.value = 5
    assert first.status() == 15 and Outer.Inner.twice(Int(3)) == 6
    previous = svx.Output()
    first.advance(Int(7), previous)
    assert previous.value == 5 and first.status() == 17
    packet = Packet()
    packet.tag.value = 0x81
    packet.flags.value = LogicValue.from_string('10xz')
    packet.mode.value = Mode.ACTIVE
    assert first.echo(packet).to_bytes() == packet.to_bytes()
    first.packet.value = packet
    first.packet.tag.value = 0x23
    assert first.packet.tag.value == 0x23
    assert first.packet.flags.value == LogicValue.from_string('10xz')
    local_packet = Outer.LocalPacket()
    local_packet.mode.value = Outer.LocalMode.LOCAL_ACTIVE
    local_packet.flags.value = LogicValue.from_string('x01z')
    assert first.echo_local(local_packet).to_bytes() == local_packet.to_bytes()
    first.local_packet.value = local_packet
    first.local_packet.mode.value = Outer.LocalMode.LOCAL_IDLE
    assert first.local_packet.mode.value == Outer.LocalMode.LOCAL_IDLE
    assert first.local_packet.flags.value == LogicValue.from_string('x01z')
    assert OtherOuter.Inner(Int(3)).status() == 25
    assert outer.Inner(Int(3)).status() == 47
    assert Outer_Inner(Int(3)).status() == 36
    if hasattr(Outer, 'Alias'):
        assert Outer.Alias(Int(3)).status() == 14
    child = PythonInner(Int(10))
    assert child.status() == 121
    svx.publish_object('scoped.child', child)
    svx.display('SCOPED_PYTHON_PASS')
