package tb_pkg;
  import m10_object_types_pkg::*;
  virtual class BaseDriver;
    function new(input int seed);
    endfunction
    virtual task drive(input int address, input string label, input Packet packet);
      $fatal(2, "base drive should be overridden by Python");
    endtask
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/m9_inheritance/mirrors.sv"

module tb;
  import m10_object_types_pkg::*;
  import svx_pkg::*;
  import svx_pyproxy_tb_pkg_pkg::*;

  class IntermediateDriver extends BaseDriver_python_proxy;
    function new(input int seed);
      super.new(seed);
    endfunction
  endclass

  class FinalDriver extends IntermediateDriver;
    function new(input int seed);
      super.new(seed);
    endfunction
  endclass

  initial begin
    FinalDriver driver;
    Packet packet;
    time before_drive;
    svx_init();
    svx_load("tests.integration.m9_inheritance_test");
    svx_start("m9.setup");
    // The generated proxy remains an ordinary SV base class: user SV classes
    // may appear between it and the final instance without changing dispatch.
    driver = new(9);
    packet = new();
    packet.address = 37;
    packet.label = "object-payload";
    before_drive = $time;
    repeat (10) begin
      driver.drive(37, "factory-driver", packet);
    end
    if ($time - before_drive != 20ns) begin
      $fatal(2, "M12 timed overrides advanced %0t instead of 20ns", $time - before_drive);
    end
    svx_start("m9.report");
    $display("M9 SV-to-Python inheritance callback passed");
    $finish;
  end
endmodule
