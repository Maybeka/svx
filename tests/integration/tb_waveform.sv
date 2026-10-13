`timescale 1ns/1ps
`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/waveform_control/dut.sv"
module tb;
  import svx_pkg::*;
  waveform_dut dut();
  waveform_leaf other(dut.clk);
  initial begin
    svx_init();
    svx_load("tests.integration.waveform_test");
    svx_start("waveform.check");
    svx_shutdown();
    $finish;
  end
endmodule
