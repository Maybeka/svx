// SPDX-License-Identifier: Apache-2.0
`ifndef SVX_UNIT_WIDTH
`define SVX_UNIT_WIDTH 13
`endif

class UnitLocal;
  int value = 22;
endclass

package unit_child_pkg;
  parameter int WIDTH = `SVX_UNIT_WIDTH;
  class Child extends unit_base_pkg::Base;
    bit [`SVX_UNIT_WIDTH-1:0] word;
    function new(int seed);
      super.new(seed);
      word = seed;
    endfunction
    virtual function int get();
      return super.get() + 1;
    endfunction
    task advance(int amount, output int previous, inout int total);
      previous = count;
      #2;
      count += amount;
      total += count;
    endtask
  endclass
  function automatic int consume(Child item);
    return item.get();
  endfunction
endpackage

module child_unit_probe;
  function automatic int read_local();
    UnitLocal item = new();
    return item.value;
  endfunction
endmodule
