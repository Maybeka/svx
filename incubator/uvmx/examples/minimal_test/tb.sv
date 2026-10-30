module tb;
  timeunit 1ns;
  timeprecision 1ps;

  initial begin
    uvmx_pkg::uvmx_init("my_tests");
    uvm_pkg::run_test();
  end
endmodule
