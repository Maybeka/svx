`include "sv/svx_pkg.sv"
`include "mirrors.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;
  import svx_pkg::*;

  initial begin
    time before_wait;
    svx_init();
    svx_load("svx_py.tests.integration.python_static_source");
    if ($test$plusargs("illegal_wait")) begin
      svx_proxy_python_static_source::Source::illegal_wait();
      $fatal(1, "STATIC_ILLEGAL_WAIT_CONTINUED");
    end
    if (svx_proxy_python_static_source::Source::scale(7) != 21)
      $fatal(1, "static function result mismatch");
    before_wait = $time;
    svx_proxy_python_static_source::Source::wait_once();
    if ($time - before_wait != 2ns) $fatal(1, "static task timing mismatch");
    svx_run_test("tests.integration.python_static_source", "run");
    if ($time != 4ns) $fatal(1, "static view task timing mismatch");
    svx_shutdown();
    $display("PYTHON_STATIC_SOURCE_PASS");
    $finish;
  end
endmodule
