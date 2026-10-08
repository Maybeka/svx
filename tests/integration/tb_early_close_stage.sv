`include "sv/svx_pkg.sv"
`include ".tmp/early_close_stage/common.svh"
`include ".tmp/early_close_stage/source.sv"
module tb;
  import svx_pkg::*;
  svx_mirror_sv_same_package_pkg_C::C receiver;
  initial begin
    svx_init();
    svx_load("tests.integration.early_close_stage_test");
    if ($test$plusargs("PYTHON_ORIGIN")) svx_start("early_close.create");
    else receiver = new();
    $fatal(1, "EARLY_CLOSED_CONSTRUCTION_UNEXPECTED_SUCCESS");
  end
endmodule
