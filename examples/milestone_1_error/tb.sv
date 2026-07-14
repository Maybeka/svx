`include "sv/svx_pkg.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  initial begin
    svx_init();
    svx_load("examples.milestone_1_error.tests.error_test");
    svx_start("examples.milestone_1_error.tests.error_test.main");
    $display("ERROR: svx_start returned after fatal test");
    $finish;
  end
endmodule
