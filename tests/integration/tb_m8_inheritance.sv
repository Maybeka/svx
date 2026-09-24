package tb_pkg;
  virtual class BaseDriver;
    virtual task drive(input int address, input int data);
    endtask
    static function int static_value();
      return 8;
    endfunction
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/m8_inheritance/mirrors.sv"

module tb;
  import svx_projection_checks_pkg::*;
  import svx_static_tb_pkg_BaseDriver_pkg::*;

  initial begin
    $display("M8 declaration-only inheritance mirrors compiled");
    $finish;
  end
endmodule
