// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`define SVX_EXAMPLE_VALUES \
  typedef enum bit[W-1:0] {ZERO=W'(0), ONE=W'(1)} Mode; \
  typedef Mode Alias; \
  typedef struct packed {Mode mode; bit[W-1:0] data;} Payload; \
  typedef bit[W-1:0] Word; \
  typedef Payload Packets[2]; \
  typedef Mode Modes[$]; \
  localparam Mode DEFAULT_MODE=ONE; \
  localparam Payload DEFAULT_PAYLOAD={ONE,{W{1'b1}}}; \
  class Holder; typedef enum bit[2:0] {SMALL=2} Tag; endclass \
  initial $display("INSTANCE_VALUE|%m|%0d|%0d|%0h|%0d|%0d", \
    W, DEFAULT_MODE, DEFAULT_PAYLOAD.data, $bits(Payload), $bits(Packets));

module scoped_values #(int W=8);
  `SVX_EXAMPLE_VALUES
endmodule

interface scoped_values_if #(int W=5);
  `SVX_EXAMPLE_VALUES
endinterface

program scoped_values_program #(int W=6);
  `SVX_EXAMPLE_VALUES
  initial #2ns;
endprogram

module tb_instance_values;
  scoped_values a();
  scoped_values b();
  scoped_values #(13) c();
  scoped_values_if bus();
  scoped_values_program p();
  for (genvar i=0;i<2;i++) begin: lanes
    typedef bit[i+2:0] Index;
    localparam int ID=i;
    initial $display("INSTANCE_INDEX|%m|%0d|%0d", ID, $bits(Index));
  end
  initial begin
    #1ns;
    $display("INSTANCE_VALUES_NATIVE_PASS");
    $finish;
  end
endmodule

`undef SVX_EXAMPLE_VALUES
