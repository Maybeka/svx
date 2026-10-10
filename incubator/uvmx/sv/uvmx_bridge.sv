`ifndef UVMX_BRIDGE__SV
`define UVMX_BRIDGE__SV

// UVM remains the scheduler and factory. SVX owns only Python hosting.
task automatic uvmx_run_test(string python_module, string explicit_test_name = "");
  string alias_name;
  string canonical_name;

  svx_init();
  svx_load(python_module);
  uvm_top.finish_on_completion = 0;

  if ($value$plusargs("UVM_TESTNAME=%s", canonical_name)) begin
    uvm_pkg::run_test();
  end else if ($value$plusargs("UVM_TEST_NAME=%s", alias_name)) begin
    `uvm_warning("UVMX/TESTNAME", "use +UVM_TESTNAME, not +UVM_TEST_NAME")
    uvm_pkg::run_test(alias_name);
  end else begin
    uvm_pkg::run_test(explicit_test_name);
  end

  svx_shutdown();
  $finish;
endtask

`endif
