module uvmx_peer_testbench;
  timeunit 1ns;
  timeprecision 1ps;

  import uvm_pkg::*;
  import svx_pkg::*;
  import uvmx_pkg::*;
  import uvmx_peer_pkg::*;
  import uvmx_generated_pkg::*;

  initial begin
    string explicit_test_name;
    if ($value$plusargs("UVMX_EXPLICIT_TEST=%s", explicit_test_name)) begin
      uvmx_run_test("python_tests", explicit_test_name);
    end else begin
      uvmx_run_test("python_tests");
    end
  end
endmodule
