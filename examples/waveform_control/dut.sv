`timescale 1ns/1ps
module waveform_leaf(input bit clk);
  int deep_count = 0;
  always @(posedge clk) deep_count++;
endmodule

module waveform_dut;
  bit clk = 0;
  int count = 0;
  always #0.5 clk = ~clk;
  always @(posedge clk) count++;
  waveform_leaf child(clk);
endmodule
