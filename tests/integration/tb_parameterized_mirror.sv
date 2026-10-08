package parameterized_pkg;
  class Base #(type T = int, int N = 2);
    T count = N;
    function T get_count();
      return count;
    endfunction
    function void set_count(T value);
      count = value;
    endfunction
    virtual function T check(T value);
      return count + value + N;
    endfunction
    function T call_check(T value);
      return check(value);
    endfunction
    virtual function void observe(output T result);
      result = count;
    endfunction
    function T call_observe();
      T result;
      observe(result);
      return result;
    endfunction
    virtual function T collisions(
      input T ok, request, response, error, bytes, offset,
      request_value, response_value, svx_ok, output T result
    );
      result = ok + request + response + error + bytes + offset + request_value + response_value + svx_ok;
      return result + 1;
    endfunction
    function T call_collisions();
      T observed;
      T returned;
      returned = collisions(1, 2, 3, 4, 5, 6, 7, 8, 9, observed);
      return returned + observed;
    endfunction
  endclass

  class Child extends Base#(int, 7);
    function int check(int value);
      return super.check(value) + 1;
    endfunction
  endclass
endpackage

`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/parameterized_mirror/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    parameterized_pkg::Child child;
    parameterized_pkg::Base#(int, 7) base_handle;
    child = new();
    base_handle = child;
    if (base_handle.check(3) != 18)
      $fatal(2, "SV override without repeated virtual lost dynamic dispatch");
    svx_init();
    svx_load("tests.integration.parameterized_mirror_test");
    svx_start("parameterized_mirror.run");
    svx_shutdown();
    $finish;
  end
endmodule
