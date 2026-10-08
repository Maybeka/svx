from __future__ import annotations

import svtypes
import svx
from tests.integration.source_value_types import Operation, ValuePacket

_scalar_callbacks = 0
_native_collection_callbacks = 0
_value_callbacks = 0


def _scalar_callback(value):
    global _scalar_callbacks
    _scalar_callbacks += 1
    return value


def _native_collection_callback(value):
    global _native_collection_callbacks
    _native_collection_callbacks += 1
    return value


def _value_callback(value):
    global _value_callbacks
    _value_callbacks += 1
    return value

@svx.sv_mirror("sv://source_discovery_pkg/Base")
class BaseStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class Derived(BaseStub):
    def __init__(self, seed: svtypes.Int):
        super().__init__(seed)

    @svx.inheritance_method
    def check(self, value: svtypes.Int) -> svx.Function[svtypes.Int]:
        return super().check(value) + 100

    @svx.inheritance_method
    def echo_byte(self, value: svtypes.Bit[8, svtypes.Signed]) -> svx.Function[svtypes.Bit[8, svtypes.Signed]]:
        return _scalar_callback(super().echo_byte(value))

    @svx.inheritance_method
    def echo_short(self, value: svtypes.Bit[16, svtypes.Signed]) -> svx.Function[svtypes.Bit[16, svtypes.Signed]]:
        return _scalar_callback(super().echo_short(value))

    @svx.inheritance_method
    def echo_unsigned(self, value: svtypes.Bit[32]) -> svx.Function[svtypes.Bit[32]]:
        return _scalar_callback(super().echo_unsigned(value))

    @svx.inheritance_method
    def echo_integer(self, value: svtypes.Logic[32, svtypes.Signed]) -> svx.Function[svtypes.Logic[32, svtypes.Signed]]:
        return _scalar_callback(super().echo_integer(value))

    @svx.inheritance_method
    def echo_time(self, value: svtypes.Logic[64]) -> svx.Function[svtypes.Logic[64]]:
        return _scalar_callback(super().echo_time(value))

    @svx.inheritance_method
    def echo_shortreal(self, value: svtypes.ShortReal) -> svx.Function[svtypes.ShortReal]:
        return _scalar_callback(super().echo_shortreal(value))

    @svx.inheritance_method
    def echo_signed_bit(self, value: svtypes.Bit[1, svtypes.Signed]) -> svx.Function[svtypes.Bit[1, svtypes.Signed]]:
        return _scalar_callback(super().echo_signed_bit(value))

    @svx.inheritance_method
    def echo_bytes(self, values: svtypes.Queue[svtypes.Bit[8, svtypes.Signed]]) -> svx.Function[svtypes.Queue[svtypes.Bit[8, svtypes.Signed]]]:
        return _native_collection_callback(super().echo_bytes(values))

    @svx.inheritance_method
    def echo_shorts(self, values: svtypes.DynArray[svtypes.Bit[16]]) -> svx.Function[svtypes.DynArray[svtypes.Bit[16]]]:
        return _native_collection_callback(super().echo_shorts(values))

    @svx.inheritance_method
    def echo_flags(self, values: svtypes.Array[svtypes.Logic[32, svtypes.Signed], 2]) -> svx.Function[svtypes.Array[svtypes.Logic[32, svtypes.Signed], 2]]:
        return _native_collection_callback(super().echo_flags(values))

    @svx.inheritance_method
    def echo_stamps(self, values: svtypes.AssocArray[svtypes.String, svtypes.Logic[64]]) -> svx.Function[svtypes.AssocArray[svtypes.String, svtypes.Logic[64]]]:
        return _native_collection_callback(super().echo_stamps(values))

    @svx.inheritance_method
    def echo_operation(self, value: Operation) -> svx.Function[Operation]:
        return _value_callback(super().echo_operation(value))

    @svx.inheritance_method
    def echo_value_packet(self, value: ValuePacket) -> svx.Function[ValuePacket]:
        return _value_callback(super().echo_value_packet(value))

    @svx.inheritance_method
    def transform(self, values: svtypes.Queue[svtypes.Int],
                  observed: svx.Output[svtypes.Queue[svtypes.Int]],
                  changed: svx.Inout[svtypes.Queue[svtypes.Int]]) -> svx.Function[svtypes.Queue[svtypes.Int]]:
        result = super().transform(values, observed, changed)
        observed.value = list(observed.value) + [200]
        changed.value = list(changed.value) + [300]
        return list(result) + [100]

    @svx.inheritance_method
    def dynamic_copy(self, values: svtypes.DynArray[svtypes.Int]) -> svx.Function[svtypes.DynArray[svtypes.Int]]:
        return list(super().dynamic_copy(values)) + [101]

    @svx.inheritance_method
    def fixed_copy(self, values: svtypes.Array[svtypes.Int, 2]) -> svx.Function[svtypes.Array[svtypes.Int, 2]]:
        result = list(super().fixed_copy(values))
        result[1] += 102
        return result

    @svx.inheritance_method
    def keyed_copy(self, values: svtypes.AssocArray[svtypes.String, svtypes.Int]) -> svx.Function[svtypes.AssocArray[svtypes.String, svtypes.Int]]:
        result = dict(super().keyed_copy(values))
        result["python"] = 103
        return result

    @svx.inheritance_method
    def echo_packet(self, value: svtypes.RemoteRef["sv://source_discovery_pkg/Packet"]) -> svx.Function[svtypes.RemoteRef["sv://source_discovery_pkg/Packet"]]:
        result = super().echo_packet(value)
        assert result.target_type_name == "sv://source_discovery_pkg/Packet"
        assert result.object_number == value.object_number
        return result

    @svx.inheritance_method
    def echo_vif(self, value: svtypes.RemoteRef["sv-vif://external_bus_if/master"]) -> svx.Function[svtypes.RemoteRef["sv-vif://external_bus_if/master"]]:
        result = super().echo_vif(value)
        result.write_data(0x52)
        assert result.read().value_mask == 0x52
        svx.display("SOURCE_DISCOVERY_VIF_CALLBACK_PASS")
        return result


_instance = None


@svx.export(name="source_discovery.create")
def create():
    global _instance
    _instance = Derived(7)
    assert _instance.check(3) == 110
    assert _instance.echo_byte(-12) == -12
    assert _instance.echo_short(-1234) == -1234
    assert _instance.echo_unsigned(0xfedcba98) == 0xfedcba98
    flags = svtypes.LogicValue(32, 1, 0x10, 0x20)
    assert _instance.echo_integer(flags) == flags
    _instance.flags.value = flags
    stamp = svtypes.LogicValue(64, 1 << 40, 1 << 50, 1 << 60)
    assert _instance.echo_time(stamp) == stamp
    assert _instance.echo_shortreal(1.25) == 1.25
    assert _instance.echo_signed_bit(-1) == -1
    assert list(_instance.echo_bytes([-128, -1, 127])) == [-128, -1, 127]
    assert list(_instance.echo_shorts([0, 0xffff])) == [0, 0xffff]
    assert list(_instance.echo_flags([flags, svtypes.LogicValue(32, 7)])) == [flags, svtypes.LogicValue(32, 7)]
    assert dict(_instance.echo_stamps({"stamp": stamp})) == {"stamp": stamp}
    assert _instance.echo_operation(Operation.RUN) == Operation.RUN
    _instance.operation.value = Operation.RUN
    packet_value = ValuePacket()
    packet_value.tag.value = 0xa5
    packet_value.flags.value = svtypes.LogicValue(4, 1, 2, 4)
    echoed = _instance.echo_value_packet(packet_value)
    assert isinstance(echoed, ValuePacket)
    assert echoed.tag.value == 0xa5
    assert echoed.flags.value == svtypes.LogicValue(4, 1, 2, 4)
    assert _instance.count.value == 7
    observed, changed = svx.Output(), svx.Inout([3])
    assert list(_instance.transform([1, 2], observed, changed)) == [1, 2, 100]
    assert list(observed.value) == [1, 2, 30, 200]
    assert list(changed.value) == [3, 40, 300]
    assert list(_instance.dynamic_copy([1, 2])) == [1, 2, 101]
    assert list(_instance.fixed_copy([3, 4])) == [3, 106]
    assert dict(_instance.keyed_copy({"caller": 5})) == {"caller": 5, "python": 103}
    packet = _instance.packet.value
    assert packet.target_type_name == "sv://source_discovery_pkg/Packet"
    assert _instance.echo_packet(packet).object_number == packet.object_number
    assert list(_instance.samples.value) == [1, 2]
    _instance.samples.value = [5, 6, 7]
    _instance.count.value = 9
    svx.publish_object("source_discovery.instance", _instance)
    svx.display("SOURCE_DISCOVERY_CREATE_PASS")


@svx.export(name="source_discovery.close")
def close():
    assert _value_callbacks == 4
    assert _instance.operation.value == Operation.RUN
    svx.display("SOURCE_DISCOVERY_VALUE_PASS")
    assert _native_collection_callbacks == 8
    svx.display("SOURCE_DISCOVERY_NATIVE_COLLECTION_PASS")
    assert _scalar_callbacks == 14
    assert _instance.flags.value == svtypes.LogicValue(32, 1, 0x10, 0x20)
    svx.display("SOURCE_DISCOVERY_SCALAR_PASS")
    assert _instance.count.value == 13
    assert list(_instance.samples.value) == [5, 6, 7, 8]
    assert _instance.check(3) == 116
    assert _instance.echo_vif(_instance.vif.value).read().value_mask == 0x52
    svx.display("SOURCE_DISCOVERY_HANDLE_PASS")
    svx.close_instance(_instance)
    svx.display("SOURCE_DISCOVERY_CLOSE_PASS")
