// SPDX-License-Identifier: Apache-2.0
package unit_base_pkg;
  typedef enum bit[2:0] {IDLE=0, ACTIVE=5} Mode;
  class Base;
    int inherited;
    function new(int seed);
      inherited = seed + 1;
    endfunction
    static function int inherited_twice(int value);
      return value * 2;
    endfunction
  endclass
endpackage

class UnitBase extends unit_base_pkg::Base;
  function new(int seed);
    super.new(seed);
  endfunction
  static function int local_twice(int value);
    return value * 2;
  endfunction
endclass

class Driver extends UnitBase;
  int count;
  function new(int seed);
    super.new(seed);
    count = seed;
  endfunction
  virtual function int status();
    return count + 1;
  endfunction
  task advance(input int value, output int previous, inout int total);
    #2ns;
    previous = count;
    total += value;
    count = value;
  endtask
  static function int twice(int value);
    return value * 2;
  endfunction
  function unit_base_pkg::Mode echo_mode(input unit_base_pkg::Mode mode);
    return mode;
  endfunction
endclass
