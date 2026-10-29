`ifndef UVMX_BRIDGE__SV
`define UVMX_BRIDGE__SV

// Complete registration before the caller enters ordinary UVM run_test().
task automatic uvmx_init(string python_module);
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
endtask

`endif
