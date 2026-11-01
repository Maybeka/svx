"""Class-scoped snapshots coexist with real SV mirrors and native constants."""
import svx

from svx_mirror.class_constants_pkg import Alias, Derived, Limits


@svx.export(name='class_constants.run')
def run():
    assert issubclass(Derived, Limits)
    first, second, alias = Limits(), Derived(), Alias()
    assert first.get_value() == second.get_value() == alias.get_value() == 8
    assert Limits.get_width() == Limits.WIDTH == Derived.WIDTH == Alias.WIDTH == 8
    assert Derived.COUNT == 16
    assert Limits.Nested.DEPTH == Alias.Nested.DEPTH == 11
    assert first.get_default() == Limits.DEFAULT_MODE == Limits.Mode.READY
    assert alias.get_default() == Alias.DEFAULT_MODE == Limits.Mode.READY
    native_packet = Limits.get_packet()
    assert native_packet.tag.value == Limits.DEFAULT_PACKET.tag.value == 0x91
    assert str(native_packet.flags.value) == str(Limits.DEFAULT_PACKET.flags.value) == '10xz'
    assert [Limits.get_table(index) for index in range(3)] == Limits.TABLE == [1, -2, 3]
    Limits.WIDTH = 99
    Limits.DEFAULT_PACKET.tag.value = 0
    Limits.TABLE[0] = 99
    assert Limits.get_width() == 8 and Limits.get_table(0) == 1
    assert Limits.get_packet().tag.value == 0x91
    assert second.get_value() == 8
    svx.display('CLASS_CONSTANTS_PYTHON_PASS')
