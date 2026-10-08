`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "tests/integration/natural_constructor_bridge_types.sv"
`include ".tmp/natural_constructor_bridge/mirrors.sv"

module tb;
  import svx_pkg::*;
  import svx_call_records_pkg::*;
  import svx_external_handles_pkg::*;
  `include ".tmp/natural_constructor_bridge/records.svh"

  CMirror first;
  BProxy second;
  natural_bridge_pkg::Packet packet;
  initial begin
    svx_init();
    svx_load("tests.integration.natural_constructor_bridge");
    svx_start("natural_bridge.setup");
    packet = new();
    first = new(7, "alpha", packet);
    second = new(17, "beta", packet);
    if (svx_construction_context::frames.size() != 0)
      $fatal(1, "natural construction retained a receiver context");
    if (first.count != 1118 || first.label != "alpha-C-B" ||
        second.count != 118 || second.label != "beta-B" ||
        first.packet != packet || second.packet != packet)
      $fatal(1, "natural typed constructor arguments or capture count failed");
    svx_start("natural_bridge.verify");
    $display("NATURAL_CONSTRUCTOR_SV_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
