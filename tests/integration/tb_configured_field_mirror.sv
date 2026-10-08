`ifdef SVX_INCLUDE_SEARCH
`include "tests/integration/include_search_owner.sv"
`else
`include "tests/integration/configured_field_owner.sv"
`endif
`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/public_macro/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.sv_field_mirror_test");
    svx_start("sv_field_mirror.run");
    svx_shutdown();
    $finish;
  end
endmodule
