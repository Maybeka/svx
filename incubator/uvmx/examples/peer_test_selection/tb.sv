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
    uvm_factory factory;
    bit expected_finish_policy;
    if ($test$plusargs("UVMX_RETURN")) uvm_top.finish_on_completion = 0;
    expected_finish_policy = uvm_top.finish_on_completion;
    uvmx_init("python_tests");
    factory = uvm_factory::get();
    if (factory.find_wrapper_by_name("py_smoke_test") == null ||
        factory.find_wrapper_by_name("legacy_sv_test") == null)
      $fatal(2, "UVMX registration did not finish before run_test");
    if (uvm_top.finish_on_completion != expected_finish_policy)
      $fatal(2, "UVMX initialization changed UVM finish policy");
    $display("UVMX_REGISTRATION_COMPLETE");
    if ($value$plusargs("UVMX_EXPLICIT_TEST=%s", explicit_test_name)) begin
      uvm_pkg::run_test(explicit_test_name);
    end else begin
      uvm_pkg::run_test();
    end
    svx_shutdown();
    $display("UVMX_NATIVE_RUN_TEST_RETURNED");
    $finish;
  end
endmodule
