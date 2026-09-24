package amirror_pkg;
  virtual class Base;
    function new();
    endfunction

    virtual task ping();
      $fatal(2, "Base.ping must be overridden by PythonChild");
    endtask
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/amirror_inheritance/mirrors.sv"

module tb;
  import amirror_pkg::*;
  import svx_pkg::*;
  import svx_projection_amirror_pkg_BaseMirror_pkg::*;

  initial begin
    BaseMirror driver;
    time before_ping;

    svx_init();
    svx_load("tests.integration.amirror_inheritance_test");
    driver = new();
    before_ping = $time;
    driver.ping();
    if ($time - before_ping != 2ns) begin
      $fatal(2, "AMirror Python override advanced %0t instead of 2ns", $time - before_ping);
    end
    $display("AMIRROR_INHERITANCE_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
