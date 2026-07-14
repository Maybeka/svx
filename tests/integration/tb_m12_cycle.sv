`include "sv/svx_pkg.sv"

class Recursive implements svx_pkg::svx_dispatchable;
  string nested_error;

  function new();
    svx_pkg::svx_inheritance_registry::register_object(77, this);
  endfunction

  task ping();
    bit ok;
    chandle request;
    chandle response;
    string error;
    byte unsigned bytes[$];
    request = svx_pkg::svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");
    svx_pkg::svx_inheritance_call_python(77, "sv://cycle/Recursive#ping", request, ok, response, error);
    svx_pkg::svx_payload_destroy(request);
    if (response != null) svx_pkg::svx_payload_destroy(response);
    if (!ok) nested_error = error;
  endtask

  virtual task svx_invoke(string method_id, input chandle request, output bit ok, output chandle response, output string error);
    nested_error = "";
    ping();
    response = null;
    ok = 0;
    error = nested_error;
  endtask
endclass

module tb;
  import svx_pkg::*;
  initial begin
    Recursive recursive;
    svx_init();
    svx_load("tests.integration.m12_cycle_test");
    svx_start("m12.setup");
    recursive = new();
    recursive.ping();
    $display("M12 negative cycle regression passed");
    $finish;
  end
endmodule
