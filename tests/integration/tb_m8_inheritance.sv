package tb_pkg;
  virtual class BaseDriver;
    virtual task drive(input int address, input int data);
    endtask
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/m8_inheritance/mirrors.sv"

module tb;
  import svx_py_checks_pkg::*;

  initial begin
    $display("M8 declaration-only inheritance mirrors compiled");
    $finish;
  end
endmodule
