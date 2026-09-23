package tb_pkg;
  virtual class BaseDriver;
    virtual task drive();
      $display("M9 SV base method called");
    endtask
    virtual function int read_count();
      return 17;
    endfunction
  endclass
endpackage
`include "sv/svx_pkg.sv"
`include ".tmp/m9_super/mirrors.sv"
module tb;
  import svx_pkg::*;
  import svx_projection_tb_pkg_pkg::*;
  initial begin
    BaseDriverMirror driver;
    svx_init();
    svx_load("tests.integration.m9_super_test");
    svx_start("m9.super_setup");
    driver = new();
    driver.drive();
    if (driver.read_count() != 19) begin
      $fatal(2, "M9 Python function override was not called");
    end
    $display("M9 Python super dispatch passed");
    $finish;
  end
endmodule
