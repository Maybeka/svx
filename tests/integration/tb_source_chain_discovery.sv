`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/source_chain_discovery/integrated/source.sv"

module tb;
  import svx_pkg::*;
  source_chain_pkg::A base_handle;
  source_chain_user_pkg::C handle;
  longint unsigned receiver_id;
  int check_revision;
  initial begin
    svx_init();
    svx_load("tests.integration.source_chain_test");
    svx_start("source_chain.create");
    `SVX_GET_OBJECT(source_chain_user_pkg::C, "source_chain.instance", handle)
    base_handle = handle;
    receiver_id = svx_inheritance_registry::published_object_ids["source_chain.instance"];
    check_revision = $test$plusargs("SOURCE_CHAIN_BODY_REVISION") ? 10 : 0;
    if (base_handle.check(5) != 10117 + check_revision || handle.compute(5) != 101008)
      $fatal(1, "source-only alternating virtual dispatch failed");
`ifdef SOURCE_CHAIN_INTERFACE_REVISION
    if (handle.bonus != 4 || handle.ping(6) != 10)
      $fatal(1, "source-only regenerated Python members failed");
`endif
    handle.count = 7;
    handle.extra = 11;
    $display("SOURCE_CHAIN_SV_PASS");
    svx_start("source_chain.close");
    if (svx_inheritance_registry::objects.exists(receiver_id))
      $fatal(1, "source-only alternating receiver was not retired");
    svx_shutdown();
    $display("SOURCE_CHAIN_DISCOVERY_PASS");
    $finish;
  end
endmodule
