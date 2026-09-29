"""Python endpoint for the external class-handle and VIF example."""

from svtypes import RemoteRef
import svx


PacketRef = RemoteRef["sv://example_packet_pkg/Packet"]
MasterRef = RemoteRef["sv-vif://example_bus_if/master"]


@svx.inheritance_class(canonical_id="py://examples/foreign_handles/HandlePortal")
class HandlePortal:
    @svx.inheritance_method(
        parameters=[
            svx.inheritance_parameter(
                "packet",
                PacketRef,
                handle=svx.sv_class_handle(
                    "sv://example_packet_pkg/Packet", "example_packet_pkg::Packet"
                ),
            ),
        ],
        return_type=PacketRef,
        return_handle=svx.sv_class_handle(
            "sv://example_packet_pkg/Packet", "example_packet_pkg::Packet"
        ),
        timing="function",
    )
    def retain_packet(self, packet):
        """Keep the opaque foreign handle and return it without introspection."""

        return packet

    @svx.inheritance_method(
        parameters=[
            svx.inheritance_parameter(
                "bus",
                MasterRef,
                handle=svx.virtual_interface_handle(
                    "sv-vif://example_bus_if/master", "virtual example_bus_if.master"
                ),
            ),
        ],
        return_type=MasterRef,
        return_handle=svx.virtual_interface_handle(
            "sv-vif://example_bus_if/master", "virtual example_bus_if.master"
        ),
        timing="function",
    )
    def exercise_bus(self, bus):
        """Use only members exported by ``example_bus_if.master``."""

        bus.write_data(0x5C)
        assert bus.read().value_mask == 0x5C
        return bus

