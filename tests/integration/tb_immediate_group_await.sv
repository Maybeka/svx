`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.immediate_group_await_test");
    svx_start("process.immediate_await");
    if ($time != 2) $fatal(1, "group wait did not preserve child completion timing");
    svx_shutdown();
    $finish;
  end
endmodule
