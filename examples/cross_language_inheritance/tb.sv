package example_driver_pkg;
  virtual class BaseDriver;
    function new();
    endfunction

    virtual task drive();
      $fatal(2, "BaseDriver.drive must be overridden by PythonDriver");
    endtask

  endclass
endpackage

`include "sv/svx_pkg.sv"
`include "examples/cross_language_inheritance/generated/inheritance_mirrors.sv"

module tb;
  import example_driver_pkg::*;
  import svx_pkg::*;

  initial begin
    BaseDriver driver;
    time before_drive;
    svx_init();
    svx_load("examples.cross_language_inheritance.python_checks");
    svx_start("inheritance.create_driver");
    `SVX_GET_OBJECT(example_driver_pkg::BaseDriver, "example.driver", driver)
    before_drive = $time;
    driver.drive();
    if ($time - before_drive != 2ns) begin
      $fatal(2, "Python override advanced %0t instead of 2ns", $time - before_drive);
    end
    svx_shutdown();
    $finish;
  end
endmodule
