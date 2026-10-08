package iteration_pkg;
  class Driver;
    int initial_value;
    function new(int ok, request, error, request_value, object_id, svx_object_id);
      initial_value = ok + request + error + request_value + object_id + svx_object_id;
    endfunction
    virtual function int check(int svx_return_value);
      return svx_return_value + 1 + initial_value;
    endfunction
    function int call_check(int svx_return_value);
      return check(svx_return_value);
    endfunction
  endclass
endpackage

`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/iteration_body/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("iteration_body_user");
    svx_start("iteration_body.run");
    svx_shutdown();
    $finish;
  end
endmodule
