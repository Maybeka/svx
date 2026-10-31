"""Inspect exported compilation-unit values without loading the SVX runtime."""
from svtypes import LogicValue
from svx_mirror_unit.unit_0 import DEPTH, INITIAL, START, Holder, Mode, Modes, Packet, PacketAlias, Word


def check():
    assert Mode.ACTIVE == START == 5 and DEPTH == 9
    assert PacketAlias is Packet
    assert INITIAL.mode.value == 5
    assert INITIAL.flags.value == LogicValue.from_string('10xz')
    assert Word().width == 13
    values = Modes()
    values.value = [Mode.IDLE, Mode.ACTIVE]
    assert values.to_bytes()
    payload = Holder.Payload()
    payload.state.value = Holder.State.ON
    payload.data.value = 0xa5
    assert Holder.Payload.__qualname__ == 'Holder.Payload'
    assert payload.state.value == 1 and payload.data.value == 0xa5
    print('UNIT_VALUES_PYTHON_PASS')


if __name__ == '__main__':
    check()
