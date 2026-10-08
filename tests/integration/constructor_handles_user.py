import os
import svtypes
import svx
from svx_mirror.constructor_handle_pkg import Holder


instances = []
transport_only = os.environ.get("SVX_CTOR_TRANSPORT_ONLY") == "1"


def check_vif(vif):
    if transport_only:
        assert not hasattr(vif, "read")
        assert vif._svx_remote_object_id != 0
    else:
        assert vif.read().value_mask == 0x2A


class PlainHolder:
    def __init__(self, packet, vif):
        self.packet = packet
        self.vif = vif
        check_vif(vif)

    def read_value(self):
        return 100


class Derived(Holder):
    def __init__(self, packet, vif):
        super().__init__(packet, vif)
        self.packet = packet
        self.vif = vif
        check_vif(vif)
        assert self.read_value() in {77, -1}
        instances.append(self)


@svx.export(name="constructor_handles.run")
def run():
    first, = instances
    second = Derived(first.packet, first.vif)
    assert second.read_value() == 77
    original_packet = second.native_packet.value
    original_vif = second.native_vif.value
    assert original_packet == first.packet
    if os.environ.get("SVX_HANDLE_ALIAS_GROUPING") == "1":
        assert second.echo_packet(original_packet) == original_packet
        assert first.echo_packet(original_packet) == original_packet
        svx.display("HANDLE_ALIAS_METHOD_RETURN_PASS")
    second.native_packet.value = svtypes.RemoteRefValue("sv://external_handle_test_pkg/Packet", 0)
    assert second.native_packet.value.object_number == 0
    second.native_packet.value = original_packet
    second.native_vif.value = original_vif
    try:
        second.native_packet.value = svtypes.RemoteRefValue("sv://external_handle_test_pkg/Packet", 999999)
    except svtypes.ExternalStorageError as error:
        assert "external handle" in str(error.__cause__)
    else:
        raise AssertionError("unknown field handle accepted")
    assert second.native_packet.value == original_packet
    svx.publish_object("constructor.second", second)
    empty = Derived(None, first.vif)
    assert empty.read_value() == -1
    try:
        Derived(svtypes.RemoteRefValue("sv://external_handle_test_pkg/Packet", 999999), first.vif)
    except RuntimeError as error:
        assert "external handle" in str(error)
    else:
        raise AssertionError("unknown constructor handle accepted")
    assert len(instances) == 3
    from svx_py.tests.integration.constructor_handles_user import PlainHolder as SelectedHolder

    selected = SelectedHolder(first.packet, first.vif)
    assert selected.read_value() == 177
    svx.publish_object("constructor.plain", selected)
    if not transport_only:
        first.vif.write_data(0x5C)
        assert second.vif.read().value_mask == 0x5C
    svx.close_instance(empty._svx_remote_object_id)
    svx.display("CONSTRUCTOR_HANDLES_PASS")
