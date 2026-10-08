`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.report_policy_test");
    svx_start("report-policy.run");
    svx_shutdown();
    $display("REPORT_POLICY_PASS");
    $finish;
  end
endmodule
