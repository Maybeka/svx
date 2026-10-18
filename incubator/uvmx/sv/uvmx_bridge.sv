`ifndef UVMX_BRIDGE__SV
`define UVMX_BRIDGE__SV

// UVM remains the scheduler and factory. SVX owns only Python hosting.
task automatic uvmx_run_test(string python_module, string explicit_test_name = "");
  string alias_name;
  string canonical_name;
  uvmx_typed_base_factory#(uvm_test) default_base;

  svx_init();
  svx_load(python_module);
  svx_load("uvmx.bootstrap");
  default_base = new();
  uvmx_base_registry::add("uvm_pkg::uvm_test", default_base);
  // Drain concurrently: the declaration count is not bounded by channel capacity.
  fork
    svx_start("uvmx.bootstrap.publish_tests");
    begin
      UvmxRegistration declaration;
      forever begin
        svx_get_UvmxRegistration("uvmx.bootstrap.registration", declaration);
        if (declaration.finished) break;
        uvmx_base_registry::register_test(declaration);
      end
    end
  join
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
