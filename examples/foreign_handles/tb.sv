`include "examples/foreign_handles/bus_if.sv"
`include "examples/foreign_handles/packet_types.sv"
`include "sv/svx_pkg.sv"
`include "examples/foreign_handles/generated/mirrors.sv"

class HandlePortalImpl extends svx_proxy_python_api::HandlePortal;
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
  import example_packet_pkg::*;
  import svx_pkg::*;

  example_bus_if bus();

  initial begin
    HandlePortalFactory factory;
    svx_dispatchable published;
    HandlePortalImpl portal;
    TaggedPacket source;
    Packet returned_packet;
    virtual example_bus_if.master returned_bus;

    svx_init();
    factory = new();
    svx_inheritance_registry::register_factory(
      "py://examples/foreign_handles/HandlePortal", factory
    );
    svx_load("examples.foreign_handles.python_test");
    svx_start("foreign_handles.run");
    svx_require_published_object("foreign-handles.portal", published);
    if (!$cast(portal, published)) $fatal(1, "unexpected Python endpoint type");

    source = new(37, "derived");
    returned_packet = portal.retain_packet(source);
    if (returned_packet != source || returned_packet.identifier != 37)
      $fatal(1, "class handle identity did not round trip");

    returned_bus = portal.exercise_bus(bus);
    if (bus.read() != 8'h5c) $fatal(1, "Python VIF view did not write the interface");
    returned_bus.write(8'ha6);
    if (bus.read() != 8'ha6) $fatal(1, "VIF handle did not round trip");

    svx_shutdown();
    $finish;
  end
endmodule
