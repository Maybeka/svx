`include "sv/svx_pkg.sv"
`include "examples/python_owned_inheritance/generated/inheritance_mirrors.sv"

class SvCounter extends svx_py_examples_python_owned_inheritance_base_monitor_pkg::BaseMonitor;
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

class SvCounterFactory implements svx_pkg::svx_factory;
  virtual task svx_create(
    longint unsigned object_id,
    input chandle request,
    output bit ok,
    output string error
  );
    svx_py_examples_python_owned_inheritance_base_monitor_pkg::BaseMonitor::constructor_request_t constructor_request;
    SvCounter counter;
    constructor_request = svx_py_examples_python_owned_inheritance_base_monitor_pkg::BaseMonitor::svx_decode_constructor_request(request);
    counter = new(object_id, constructor_request.seed);
    ok = 1;
    error = "";
  endtask
endclass

module tb;
  import svx_pkg::*;

  initial begin
    SvCounterFactory factory;
    svx_init();
    factory = new();
    svx_inheritance_registry::register_factory(
      "py://examples/python_owned_inheritance/base_monitor/BaseMonitor",
      factory
    );
    svx_load("examples.python_owned_inheritance.python_test");
    svx_start("python-owned-inheritance.run");
    svx_shutdown();
    $finish;
  end
endmodule
