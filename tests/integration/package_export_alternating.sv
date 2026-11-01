`timescale 1ns/1ps
`include "sv/svx_defs.svh"
package export_chain_pkg;
  int chain_allocations;
  int native_allocations;
  class A;
    int seed = 11;
    function new(); chain_allocations++; endfunction
    virtual function int check(); return seed; endfunction
  endclass
  `SVX_PY_PROXY(BProxy, "py://tests/integration/package_export_alternating/B", A)
  class C extends BProxy;
    int extra = 100;
    function new(); super.new(); endfunction
    virtual function int check(); return super.check() + extra; endfunction
  endclass
  class CLeaf extends C;
    int leaf = 7;
    function new(); super.new(); endfunction
    virtual function int check(); return super.check() + leaf; endfunction
  endclass
  class NativeBase;
    int value = 41;
    function new(); native_allocations++; endfunction
    virtual function int check(); return value; endfunction
  endclass
  class NativeDriver extends NativeBase;
    function new(); super.new(); endfunction
    virtual function int check(); return super.check() + 1; endfunction
  endclass
endpackage
