// SPDX-License-Identifier: Apache-2.0
interface array_dimensions_bus;
  bit [7:0] values[4];
  bit [2:0][7:0] vectors[2][3];
  modport access(inout values, vectors);
endinterface

package array_dimensions_pkg;
  typedef virtual array_dimensions_bus.access Bus;
  class Owner;
    local static Bus selected;
    static function void set_bus(Bus bus);
      selected = bus;
    endfunction
    static function Bus get_bus();
      return selected;
    endfunction
  endclass
endpackage
