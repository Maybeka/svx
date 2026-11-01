`include "tests/integration/external_bus_if.sv"

package external_handle_test_pkg;
  class Packet;
    int unsigned packet_id;

    function new(int unsigned packet_id = 0);
      this.packet_id = packet_id;
    endfunction
  endclass

  class TaggedPacket extends Packet;
    string tag;

    function new(int unsigned packet_id, string tag);
      super.new(packet_id);
      this.tag = tag;
    endfunction
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/external_handles/mirrors.sv"

class HandlePortalImpl extends svx_proxy_external_handle_base::HandlePortal;
  function new(longint unsigned object_id);
    super.new(object_id);
  endfunction
endclass

class HandlePortalFactory implements svx_pkg::svx_factory;
  virtual function void svx_create(
    longint unsigned object_id,
    input chandle request,
    output bit ok,
    output string error
  );
    HandlePortalImpl portal;
    portal = new(object_id);
    ok = 1;
    error = "";
  endfunction
endclass

module tb;
  import external_handle_test_pkg::*;
  import svx_pkg::*;
  import svtypes_pkg::*;
  import svx_external_handles_pkg::*;

  external_bus_if bus();

  initial begin
    HandlePortalFactory factory;
    svx_dispatchable published;
    HandlePortalImpl portal;
    TaggedPacket source;
    Packet returned_packet;
    virtual external_bus_if.master returned_vif;
    remote_ref old_reference, new_reference, null_reference, wrong_reference;
    string error;
    string python_module;

    svx_init();
    factory = new();
    svx_inheritance_registry::register_factory(
      "py://tests/integration/external_handle_base/HandlePortal", factory
    );
    if (!$value$plusargs("SVX_TEST_MODULE=%s", python_module))
      python_module = "tests.integration.external_handle_test";
    svx_load(python_module);
    svx_start("external_handles.run");
    svx_require_published_object("external-handles.portal", published);
    if (!$cast(portal, published)) $fatal(1, "published portal has wrong SV type");

    source = new(37, "derived");
    returned_packet = portal.round_trip_packet(source);
    if (returned_packet != source) $fatal(1, "class handle did not round trip");
    if (returned_packet.packet_id != 37) $fatal(1, "class handle state changed");

    bus.ready = 1'b1;
    returned_vif = portal.round_trip_vif(bus);
    if (bus.read() != 8'h5c) $fatal(1, "Python virtual-interface view did not write signal state");
    returned_vif.write(8'ha6);
    if (bus.read() != 8'ha6) $fatal(1, "virtual interface handle did not round trip");

    null_reference = SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::encode(null);
    if (!SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::decode(null_reference, returned_packet, error))
      $fatal(1, "null handle decode failed");
    if (returned_packet != null) $fatal(1, "null handle became non-null");
    old_reference = SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::encode(source);
    wrong_reference = new("sv://other/Packet", old_reference.object_number);
    if (SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::decode(wrong_reference, returned_packet, error))
      $fatal(1, "wrong target accepted");
    svx_external_handle_registry::clear();
    if (SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::endpoints.size() != 0)
      $fatal(1, "shutdown retained generated endpoints");
    if (SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::decode(old_reference, returned_packet, error))
      $fatal(1, "stale handle accepted");
    new_reference = SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::encode(source);
    if (new_reference.object_number == old_reference.object_number)
      $fatal(1, "new session reused stale id");
    if (!SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::decode(new_reference, returned_packet, error))
      $fatal(1, "retained SV handle could not be encoded in new session");
    if (returned_packet != source) $fatal(1, "new session changed handle identity");
    svx_shutdown();
    if (SVXExternal_sv_c_s_sexternal_uhandle_utest_upkg_sPacket::endpoints.size() != 0)
      $fatal(1, "shutdown retained generated endpoints");
    $display("EXTERNAL_HANDLES_PASS");
    $finish;
  end
endmodule
