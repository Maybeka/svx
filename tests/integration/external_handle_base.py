class HandlePortal:
    """Python implementation used by the generated external-handle gateway."""

    def round_trip_packet(self, packet):
        assert packet.target_type_name == "sv://external_handle_test_pkg/Packet"
        assert packet.object_number != 0
        return packet

    def round_trip_vif(self, vif):
        from svx_vif.external_bus_if.master import Master

        assert isinstance(vif, Master)
        assert vif.read_ready().value_mask == 1
        vif.write_data(0x5C)
        assert vif.read().value_mask == 0x5C
        return vif
