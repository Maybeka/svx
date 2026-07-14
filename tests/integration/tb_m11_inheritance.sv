`include "sv/svx_pkg.sv"
`include ".tmp/m11_inheritance/mirrors.sv"

class SvCounter extends svx_py_tests_integration_m11_base_pkg::BaseMonitor;
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
  virtual task svx_create(longint unsigned object_id, input chandle request, output bit ok, output string error);
    byte unsigned bytes[$];
    int offset;
    int seed;
    SvCounter counter;
    svx_pkg::svx_payload_to_byte_queue(request, bytes);
    offset = 0;
    svtypes_pkg::int_packer::unpack(seed, bytes, offset);
    counter = new(object_id, seed);
    ok = 1;
    error = "";
  endtask
endclass

module tb;
  import svx_pkg::*;
  initial begin
    SvCounter counter;
    SvCounterFactory factory;
    svx_init();
    factory = new();
    svx_inheritance_registry::register_factory("py://tests/integration/m11_base/BaseMonitor", factory);
    svx_load("tests.integration.m11_inheritance_test");
    svx_start("m11.run");
    svx_shutdown();
    svx_start("m11.after_shutdown");
    $display("M11 Python-to-SV dispatch passed");
    $finish;
  end
endmodule
