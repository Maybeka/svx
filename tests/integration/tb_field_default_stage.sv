`include "sv/svx_pkg.sv"
`include ".tmp/field_default_stage/common.svh"
`include ".tmp/field_default_stage/source.sv"
module tb;
  import svx_pkg::*;
  svx_mirror_sv_same_package_pkg_C::C receiver;
  initial begin
    svx_init();
    svx_load("tests.integration.field_default_stage_test");
    receiver = new();
    if (receiver.retry != 23 || receiver.observed != 23 || receiver.check() != 135)
      $fatal(1, "SV declaration initializer overwrote the Python constructor assignment");
    svx_start("field_default.verify_sv");
    svx_start("field_default.create");
    if (same_package_pkg::A::allocations != 2 ||
        svx_inheritance_registry::objects.num() != 0 ||
        svx_construction_context::frames.size() != 0)
      $fatal(1, "field initializer test leaked a construction receiver");
    svx_shutdown();
    $display("FIELD_DEFAULT_STAGE_PASS");
    $finish;
  end
endmodule
