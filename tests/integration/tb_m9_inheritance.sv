package tb_pkg;
  import m10_object_types_pkg::*;
  virtual class BaseDriver;
    function new(input int seed);
    endfunction
    virtual task drive(input int address, inout int changed, output int observed, input string label, input Packet packet);
      $fatal(2, "base drive should be overridden by Python");
    endtask
    virtual function int calculate(input int source, inout int changed, output int observed);
      $fatal(2, "base calculate should be overridden by Python");
    endfunction
    function int base_value();
      return 18;
    endfunction
    static function int static_value();
      return 71;
    endfunction
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/m9_inheritance/mirrors.sv"

module tb;
  import m10_object_types_pkg::*;
  import svx_pkg::*;
  import svx_projection_tb_pkg_BaseDriverMirror_pkg::*;

  class IntermediateDriver extends BaseDriverMirror;
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
    int changed;
    int observed;
    int result;
    time before_drive;
    svx_init();
    svx_load("tests.integration.m9_inheritance_test");
    svx_start("m9.setup");
    // User SV classes may appear after AMirror without changing virtual
    // dispatch to the paired Python instance.
    driver = new(9);
    packet = new();
    packet.address = 37;
    packet.label = "object-payload";
    changed = 10;
    before_drive = $time;
    repeat (10) begin
      driver.drive(37, changed, observed, "factory-driver", packet);
    end
    if ($time - before_drive != 20ns) begin
      $fatal(2, "M12 timed overrides advanced %0t instead of 20ns", $time - before_drive);
    end
    if (changed != 20 || observed != 57) begin
      $fatal(2, "M9 copy-out parameters were changed=%0d observed=%0d", changed, observed);
    end
    if (driver.base_value() != 18) begin
      $fatal(2, "M9 non-virtual SV call did not retain the BaseDriver implementation");
    end
    if (tb_pkg::BaseDriver::static_value() != 71) begin
      $fatal(2, "M9 static SV call did not retain the BaseDriver implementation");
    end
    changed = 10;
    result = driver.calculate(4, changed, observed);
    if (changed != 14 || observed != 44 || result != 45) begin
      $fatal(2, "M9 function copy-out was changed=%0d observed=%0d result=%0d", changed, observed, result);
    end
    svx_start("m9.report");
    $display("M9 SV-to-Python inheritance callback passed");
    $finish;
  end
endmodule
