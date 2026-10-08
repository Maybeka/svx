`include "sv/svx_pkg.sv"
`include "tests/integration/external_bus_if.sv"
`include ".tmp/inline_endpoint/common.svh"
`include ".tmp/inline_endpoint/source.sv"

module tb;
  import svx_pkg::*;
  import svtypes_pkg::*;
  typedef svx_external_handles_pkg::SVXExternal_sv___external_handle_test_pkg_Packet PacketAdapter;
  typedef svx_external_handles_pkg::SVXExternal_sv_vif___external_bus_if_master VifAdapter;
  external_bus_if bus();
  external_handle_test_pkg::Packet packet, decoded;
  virtual external_bus_if.master vif, decoded_vif;
  remote_ref first, second, vif_ref;
  string error;
  initial begin
    packet = new(71);
    first = PacketAdapter::encode(packet);
    second = external_handle_test_pkg::SVXExternal_sv___external_handle_test_pkg_Packet::encode(packet);
    if (first.object_number != second.object_number || svx_external_handle_registry::objects.num() != 1)
      $fatal(1, "endpoint alias split object identity");
    if (!PacketAdapter::decode(first, decoded, error) || decoded != packet)
      $fatal(1, "same-package endpoint lost class handle");
    decoded.packet_id = 93;
    if (packet.packet_id != 93) $fatal(1, "endpoint copied concrete object");
    vif = bus;
    vif_ref = VifAdapter::encode(vif);
    if (!VifAdapter::decode(vif_ref, decoded_vif, error) || decoded_vif != vif)
      $fatal(1, "same-package endpoint lost interface handle");
    decoded_vif.data = 8'h5c;
    if (bus.data != 8'h5c) $fatal(1, "interface handle does not reference source instance");
    svx_external_handle_registry::clear();
    svx_inheritance_registry::clear();
    if (PacketAdapter::decode(first, decoded, error) || VifAdapter::decode(vif_ref, decoded_vif, error))
      $fatal(1, "cleared inline endpoint stayed valid");
    if (svx_external_handle_registry::objects.num() != 0 || PacketAdapter::endpoints.size() != 0
        || VifAdapter::endpoints.size() != 0)
      $fatal(1, "inline endpoint resources leaked");
    $display("INLINE_ENDPOINT_IDENTITY_PASS");
    $finish;
  end
endmodule
