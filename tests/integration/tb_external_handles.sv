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
  virtual task svx_create(
    longint unsigned object_id,
    input chandle request,
    output bit ok,
    output string error
  );
    HandlePortalImpl portal;
    portal = new(object_id);
    ok = 1;
    error = "";
  endtask
endclass

module tb;
  import external_handle_test_pkg::*;
  import svx_pkg::*;

  external_bus_if bus();

  initial begin
    HandlePortalFactory factory;
    svx_dispatchable published;
    HandlePortalImpl portal;
    TaggedPacket source;
    Packet returned_packet;
    virtual external_bus_if.master returned_vif;

    svx_init();
    factory = new();
    svx_inheritance_registry::register_factory(
      "py://tests/integration/external_handle_base/HandlePortal", factory
    );
    svx_load("tests.integration.external_handle_test");
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

    $display("EXTERNAL_HANDLES_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
