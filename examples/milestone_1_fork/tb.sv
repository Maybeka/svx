`include "sv/svx_pkg.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  initial begin
    $display("FORK TEST realtime before SVX: %0.3f ns", $realtime);
    svx_init();
    svx_load("examples.milestone_1_fork.tests.fork_test");
    svx_start("examples.milestone_1_fork.tests.fork_test.main");
    $display("FORK TEST realtime after SVX: %0.3f ns", $realtime);
    $finish;
  end
endmodule
