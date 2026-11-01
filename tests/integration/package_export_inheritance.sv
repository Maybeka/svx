`timescale 1ns/1ps
`include "sv/svx_defs.svh"
package export_base_pkg;
  int base_constructions;
  class Base;
    int seed;
    function new(int seed);
      base_constructions++;
      this.seed = seed;
    endfunction
    virtual function int status(); return seed; endfunction
    function int identity(); return 10; endfunction
  endclass
endpackage
package export_driver_pkg;
  import export_base_pkg::*;
  int driver_constructions;
  class Driver extends Base;
    function new(int seed);
      super.new(seed);
      driver_constructions++;
    endfunction
    virtual function int status(); return super.status() + 1; endfunction
    function int identity(); return 20; endfunction
    task advance(output int previous, inout int total);
      #1ns;
      previous = seed;
      seed++;
      total += seed;
    endtask
  endclass
endpackage
