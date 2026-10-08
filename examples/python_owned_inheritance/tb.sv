`include "sv/svx_pkg.sv"
`include "examples/python_owned_inheritance/generated/inheritance_mirrors.sv"

class SvCounter extends svx_proxy_base_monitor::BaseMonitor;
  int calls;
  int seed;

  function new(longint unsigned object_id, int seed);
    super.new(object_id);
    calls = 0;
    this.seed = seed;
  endfunction

  virtual function int sample();
    calls++;
    return super.sample() + 25;
  endfunction

  virtual task notify();
    super.notify();
  endtask
endclass

module tb;
  import svx_pkg::*;

  initial begin
    svx_proxy_base_monitor::BaseMonitorFactory#(SvCounter) factory;
    svx_init();
    factory = new();
    svx_load("examples.python_owned_inheritance.python_test");
    svx_start("python-owned-inheritance.run");
    svx_shutdown();
    $display("PYTHON_OWNED_INHERITANCE_PASS");
    $finish;
  end
endmodule
