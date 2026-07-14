`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv"

module tb_type_mismatch;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  initial begin
    M7BusReq req;
    M7BusRsp rsp;

    $display("M7 type-mismatch test start @ %0.3f ns", $realtime);

    svx_init();

    rsp = new();
    rsp.id = 99;
    rsp.ok = 1'b1;
    rsp.data = 32'h12345678;
    svx_put_M7BusRsp("m7.bad.req", rsp);

    svx_get_M7BusReq("m7.bad.req", req);
    $fatal(2, "M7 type-mismatch test should not reach this line");
  end
endmodule
