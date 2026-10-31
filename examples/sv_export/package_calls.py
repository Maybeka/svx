"""Call original package functions/tasks without exporting a carrier class."""
import svx
from svtypes import Int, LogicValue, RemoteRefValue
from svx_mirror.export_driver_pkg import (
    Mode, Packet, add, bus_ready, clear, echo_packet, get_bus, invoke_sv, make_other, other_tag, same_other, step,
)
from svx_mirror.export_base_pkg import Mode as BaseMode


@svx.export(name='sv_export.package_calls')
def run():
    assert clear() is None
    assert invoke_sv(Int(7)) == 16
    previous = svx.Output()
    assert add(Int(2), Int(3), previous) == 23
    assert previous.value == 0
    total = svx.Inout(10)
    assert step(Int(4), previous, total) is None
    assert previous.value == 1 and total.value == 15
    packet = Packet()
    packet.tag.value = 0x81
    packet.flags.value = LogicValue.from_string('10xz')
    packet.mode.value = Mode.ACTIVE
    packet.base_mode.value = BaseMode.BASE_ACTIVE
    result = echo_packet(packet)
    assert result.to_bytes() == packet.to_bytes()
    first = make_other(Int(77))
    second = make_other(Int(88))
    assert isinstance(first, RemoteRefValue)
    assert first.target_type_name == 'sv://export_driver_pkg/Other'
    assert first.object_number != second.object_number
    assert other_tag(first) == 77 and other_tag(second) == 88
    assert same_other(first, first) == 1 and same_other(first, second) == 0
    bus = get_bus()
    assert bus.read_ready() == 1 and bus_ready(bus) == 1
    svx.display('PACKAGE_CALLS_PYTHON_PASS')
