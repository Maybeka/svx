"""Closed class aliases retain native widths, nominal types and virtual dispatch."""
import svtypes
import svx
import svx_mirror.generic_class_constants_pkg as exported
from svx_mirror.generic_class_constants_pkg import Child, Narrow, Same, Wide
from svx_mirror.generic_constants_types_pkg import Item, State


class PythonWide(Wide):
    def score(self, arg):
        return super().score(arg) + 100


@svx.export(name='generic_class_values.run')
def run():
    if isinstance(getattr(exported, 'Config', None), type):
        Config = exported.Config
        default = Config()
        assert default.get_value() == Config.WIDTH == Config.get_width() == 8
        assert Config.COUNT == 9 and Config.DEFAULT_ITEM == 0
        assert str(Config.get_packet().data.value) == 'x' * 8
    assert issubclass(Child, Narrow)
    assert Narrow.Mode is Same.Mode is Child.Mode
    assert Narrow.T is Same.T is Wide.T is Item
    assert svtypes.schema_descriptor(Narrow.Mode).to_dict()['schema']['width'] == 9
    assert svtypes.schema_descriptor(Wide.Mode).to_dict()['schema']['width'] == 70
    narrow, wide, same, child = Narrow(), Wide(), Same(), Child()
    assert narrow.get_value() == same.get_value() == child.get_value() == 9
    assert wide.get_value() == 70
    assert Narrow.get_width() == 9 and Wide.get_width() == 70
    assert narrow.echo_mode(Narrow.Mode.READY) == Narrow.Mode.READY
    assert wide.echo_mode(Wide.Mode.READY) == Wide.Mode.READY
    assert str(Narrow.get_packet().data.value) == 'x' * 9
    assert str(Wide.get_packet().data.value) == 'x' * 70
    assert Narrow.get_item().state.value == Wide.get_item().state.value == State.OFF
    for instance, owner, width in ((narrow, Narrow, 9), (wide, Wide, 70)):
        packet = owner.Packet()
        packet.data.value = svtypes.LogicValue.from_string('1' + 'x' * (width - 2) + 'z')
        packet.mode.value = owner.Mode.READY
        result, count = svx.Output(), svx.Inout(7)
        instance.pass_packet(packet, result, count)
        assert str(result.value.data.value) == str(packet.data.value)
        assert result.value.mode.value == owner.Mode.READY
        assert count.value == 8
    if hasattr(Narrow, 'WIDTH'):
        assert Narrow.WIDTH == Child.WIDTH == 9 and Wide.WIDTH == 70
        assert Narrow.COUNT == 10 and Wide.COUNT == 71
        assert str(Narrow.DEFAULT_PACKET.data.value) == 'x' * 9
        assert str(Wide.DEFAULT_PACKET.data.value) == 'x' * 70
        assert Wide.DEFAULT_ITEM.state.value == State.OFF
    overridden = PythonWide()
    assert overridden.score(1) == 171
    svx.publish_object('generic.wide', overridden)
    svx.display('GENERIC_CLASS_VALUES_PYTHON_PASS')
