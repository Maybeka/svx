"""Native specialization identity, parameter-bound arrays and task copy-out."""
import svx
from svx_mirror.parameterized_vif_pkg import Owner
from svx_mirror.parameterized_vif_types_pkg import Mode, Payload


@svx.export(name='parameterized_vif.run')
def run():
    default = Owner.get_default()
    same = Owner.get_same()
    wide = Owner.get_wide()
    typed = Owner.get_typed()
    assert type(default) is type(same)
    assert type(default) is not type(wide)
    assert type(typed) is not type(wide)
    assert type(typed) is type(Owner.get_alias())
    default.write_data(0xAB)
    assert same.read_data() == 0xAB
    wide.write_data(0x1234)
    typed.write_data(0x65)
    assert wide.read_data() == 0x1234
    assert typed.read_data() == 0x65
    default.write_lanes([1, 2, 3])
    wide.write_lanes([0x1234, 0x1FFF])
    assert default.read_lanes() == [1, 2, 3]
    assert wide.read_lanes() == [0x1234, 0x1FFF]
    assert default.echo(0xEF) == 0xEF
    assert wide.echo(0x1ABC) == 0x1ABC
    assert typed.echo(0x76) == 0x76
    for bus, value, size in ((default, 0x9A, 3), (wide, 0x1234, 2), (typed, 0x56, 2)):
        result = svx.Output()
        count = svx.Inout(10)
        bus.exchange(value, result, count)
        assert result.value == value
        assert count.value == 10 + size
        assert bus.read_data() == value
    enums = Owner.get_enum()
    enums.write_data(Mode.ACTIVE)
    assert enums.read_data() == Mode.ACTIVE
    assert enums.echo(Mode.IDLE) == Mode.IDLE
    structs = Owner.get_struct()
    payload = Payload()
    payload.data.value = 0xA5
    structs.write_data(payload)
    assert structs.read_data().data.value == 0xA5
    assert structs.echo(payload).data.value == 0xA5
    svx.display('PARAMETERIZED_VIF_PYTHON_PASS')
