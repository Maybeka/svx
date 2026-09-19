package example_driver_pkg;
  virtual class BaseDriver;
    function new(input int seed);
    endfunction

    virtual task drive(input int address);
      $fatal(2, "BaseDriver.drive must be overridden by PythonDriver");
    endtask
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include "examples/cross_language_inheritance/generated/inheritance_mirrors.sv"

module tb;
  import example_driver_pkg::*;
  import svx_pkg::*;
  import svx_pyproxy_example_driver_pkg_pkg::*;

  initial begin
    BaseDriver_python_proxy driver;
    time before_drive;

    svx_init();
    svx_load("examples.cross_language_inheritance.python_checks");
    driver = new(9);
    before_drive = $time;
    driver.drive(32'h40);
    if ($time - before_drive != 2ns) begin
      $fatal(2, "Python override advanced %0t instead of 2ns", $time - before_drive);
    end
    svx_start("inheritance.report");
    svx_shutdown();
    $finish;
  end
endmodule
