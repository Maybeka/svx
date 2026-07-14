`include "sv/svx_pkg.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  initial begin
    $display("SV realtime before SVX: %0.3f ns", $realtime);
    svx_init();
    svx_load("examples.milestone_1_basic.tests.basic_test");
    svx_start("examples.milestone_1_basic.tests.basic_test.main");
    $display("SV realtime after SVX: %0.3f ns", $realtime);
    $finish;
  end
endmodule
