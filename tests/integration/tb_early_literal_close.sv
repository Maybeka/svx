`include "sv/svx_pkg.sv"
`include ".tmp/early_constructor/common.svh"
`include ".tmp/early_constructor/source.sv"
module tb;
  import svx_pkg::*;
  svx_mirror_sv_same_package_pkg_A::A receiver;
  initial begin
    svx_init();
    svx_load("tests.integration.early_literal_close_test");
    if ($test$plusargs("PYTHON_ORIGIN")) svx_start("early_literal_close.create");
    else receiver = new();
    $fatal(1, "EARLY_LITERAL_CLOSED_UNEXPECTED_SUCCESS");
  end
endmodule
