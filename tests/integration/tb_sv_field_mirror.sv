`include "svtypes_pkg.sv"
`define SVX_DEEP_FIELD_AUDIT
`include "tests/integration/sv_field_owner.sv"
`undef SVX_DEEP_FIELD_AUDIT
`include "sv/svx_pkg.sv"
`include ".tmp/sv_field_mirror/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.sv_field_mirror_test");
    svx_start("sv_field_mirror.run");
    $display("SVX_MIRROR_SHUTDOWN_BEGIN");
    svx_shutdown();
    $display("SVX_MIRROR_SHUTDOWN_END");
    $finish;
  end
endmodule
