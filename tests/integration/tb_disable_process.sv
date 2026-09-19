`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  initial begin
    svx_init();
    svx_load("tests.integration.disable_process_test");
    svx_start("disable_process.run");
    svx_shutdown();
    $finish;
  end
endmodule
