"""Package functions need only their closed value types, not class mirrors."""
import svtypes
import svx
from svx_mirror.generic_class_constants_pkg import Narrow, Wide, default_packet, narrow_echo, wide_echo, wide_packet


@svx.export(name='generic_class_calls.run')
def run():
    assert not isinstance(Narrow, type) and not isinstance(Wide, type)
    assert svtypes.schema_descriptor(Narrow.Mode).to_dict()['schema']['width'] == 9
    assert narrow_echo(Narrow.Mode.READY) == Narrow.Mode.READY
    assert str(default_packet().data.value) == 'x' * 8
    packet = wide_packet()
    assert str(packet.data.value) == 'x' * 70
    packet.data.value = svtypes.LogicValue.from_string('1' + 'z' * 69)
    result = svx.Output()
    wide_echo(packet, result)
    assert str(result.value.data.value) == '1' + 'z' * 69
    assert result.value.mode.value == Wide.Mode.READY
    svx.display('GENERIC_CLASS_VALUES_PYTHON_PASS')
