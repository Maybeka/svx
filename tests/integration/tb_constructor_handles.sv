`include "tests/integration/external_bus_if.sv"

`ifdef SVX_HANDLE_ALIAS_SOURCE
`include "tests/integration/constructor_handle_alias_types.sv"
`else
`include "tests/integration/constructor_handle_types.sv"
`endif

`include "sv/svx_pkg.sv"
`include ".tmp/constructor_handles/mirrors.sv"

class PlainHolderImpl extends svx_proxy_constructor_handles_user::PlainHolder;
  external_handle_test_pkg::Packet packet;
  virtual external_bus_if.master vif;
  function new(longint unsigned object_id, external_handle_test_pkg::Packet packet,
               virtual external_bus_if.master vif);
    super.new(object_id);
    this.packet = packet;
    this.vif = vif;
  endfunction
  virtual function int read_value();
    return packet.packet_id + super.read_value();
  endfunction
endclass

module tb;
  import svx_pkg::*;
  external_bus_if bus();
  initial begin
    external_handle_test_pkg::Packet packet;
    svx_mirror_sv_constructor_handle_pkg_Holder::Holder first;
    constructor_handle_pkg::Holder second;
    svx_dispatchable published;
    PlainHolderImpl selected;
    svx_proxy_constructor_handles_user::PlainHolderFactory#(PlainHolderImpl) factory;
    bus.data = 8'h2a;
    packet = new(77);
    svx_init();
    factory = new();
    svx_load("tests.integration.constructor_handles_user");
    first = new(packet, bus);
    if (first.packet != packet) $fatal(1, "SV constructor changed packet identity");
    svx_start("constructor_handles.run");
    svx_require_published_object("constructor.second", published);
    if (!$cast(second, published)) $fatal(1, "Python constructor returned wrong SV type");
    if (second.packet != packet) $fatal(1, "Python constructor changed packet identity");
    if (second.native_packet != packet || second.native_vif != first.vif)
      $fatal(1, "field write changed native handle identity");
    svx_require_published_object("constructor.plain", published);
    if (!$cast(selected, published)) $fatal(1, "implementation-selection constructor returned wrong type");
    if (selected.packet != packet) $fatal(1, "implementation-selection constructor changed packet identity");
    if (second.vif != first.vif || selected.vif != first.vif)
      $fatal(1, "constructor changed virtual interface identity");
    if ($test$plusargs("SVX_CTOR_TRANSPORT_ONLY")) begin
      if (bus.data != 8'h2a) $fatal(1, "transport-only VIF unexpectedly changed state");
      selected.vif.write(8'h5c);
    end
    if (bus.data != 8'h5c) $fatal(1, "constructor VIF view did not share the original interface");
    svx_shutdown();
    $display("CONSTRUCTOR_HANDLE_IDENTITY_PASS");
    $finish;
  end
endmodule
