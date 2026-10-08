from __future__ import annotations

import svtypes
import svx


@svx.sv_mirror("sv://unnamed_specialization_pkg/ByteChild")
class ByteStub(svx.SVMirror):
    pass


@svx.sv_mirror("sv://unnamed_specialization_pkg/ShortChild")
class ShortStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class ByteDerived(ByteStub):
    def __init__(self, value: svtypes.Bit[8, svtypes.Signed]):
        super().__init__(value)

    @svx.inheritance_method
    def echo(self, value: svtypes.Bit[8, svtypes.Signed]) -> svx.Function[svtypes.Bit[8, svtypes.Signed]]:
        return super().echo(value) + 1


@svx.inheritance_class()
class ShortDerived(ShortStub):
    def __init__(self, value: svtypes.Bit[16]):
        super().__init__(value)

    @svx.inheritance_method
    def echo(self, value: svtypes.Bit[16]) -> svx.Function[svtypes.Bit[16]]:
        return super().echo(value) + 2


_instances = []


@svx.export(name="unnamed_specialization.create")
def create():
    assert ByteDerived.construction_count() == 0
    assert ByteDerived.width() == 5
    assert ShortDerived.width() == 99
    assert ByteDerived.static_echo(-12) == -12
    assert ShortDerived.static_echo(60000) == 60000
    assert ByteDerived.construction_count() == 0
    svx.display("UNNAMED_SPECIALIZATION_STATIC_PASS")
    byte = ByteDerived(-12)
    short = ShortDerived(60000)
    assert ByteDerived.construction_count() == 2
    _instances.extend((byte, short))
    assert byte.item.value == -12 and short.item.value == 60000
    assert byte.flags.value == 31 and short.flags.value == 131071
    byte.item.value = -23
    short.item.value = 65535
    assert byte.echo(-9) == -8 and short.echo(65000) == 65002
    svx.publish_object("unnamed.byte", byte)
    svx.publish_object("unnamed.short", short)
    svx.display("UNNAMED_SPECIALIZATION_CREATE_PASS")


@svx.export(name="unnamed_specialization.close")
def close():
    for instance in _instances:
        svx.close_instance(instance._svx_remote_object_id)
    _instances.clear()
    svx.display("UNNAMED_SPECIALIZATION_CLOSE_PASS")
