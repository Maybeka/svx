// SPDX-License-Identifier: Apache-2.0
`define SVX_UNIT_WIDTH 5

class UnitLocal;
  int value = 11;
endclass

package unit_base_pkg;
  parameter int WIDTH = `SVX_UNIT_WIDTH;
  class Base;
    int count;
    function new(int seed);
      count = seed;
    endfunction
    virtual function int get();
      return count;
    endfunction
  endclass
endpackage

module base_unit_probe;
  function automatic int read_local();
    UnitLocal item = new();
    return item.value;
  endfunction
endmodule
