`include "sv/svx_pkg.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;
  import svx_pkg::*;

  initial begin
    svx_init();
    svx_load("tests.integration.wait_isolation_test");
    svx_start("wait_isolation.run");
    svx_shutdown();
    $display("SVX_WAIT_ISOLATION_SHUTDOWN_PASS");
    $finish;
  end

  initial begin
    #100ns;
    $fatal(2, "wait isolation test timed out");
  end
endmodule
