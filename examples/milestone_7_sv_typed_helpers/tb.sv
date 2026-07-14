`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/milestone_7_sv_typed_helpers/generated/types_and_channels.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  localparam int NUM_TX = 2;

  bit clk;
  bit bus_valid;
  M7BusOp bus_op;
  int bus_id;
  bit [7:0] bus_addr;
  bit [31:0] bus_data;
  bit [31:0] mem [int unsigned];

  initial begin
    clk = 0;
    forever #(0.5ns) clk = ~clk;
  end

  task automatic existing_style_driver();
    M7BusReq req;
    M7BusReq no_req;
    M7BusRsp rsp;
    bit ok;
    bit [31:0] read_data;

    svx_try_get_M7BusReq("m7.empty.req", ok, no_req);
    if (ok) begin
      $fatal(2, "svx_try_get_M7BusReq unexpectedly found payload on empty channel");
    end

    for (int i = 0; i < NUM_TX; i++) begin
      svx_get_M7BusReq("m7.bus.req", req);

      if (req.op == M7_OP_WRITE) begin
        mem[req.addr] = req.data;
        read_data = req.data;
      end else begin
        read_data = mem.exists(req.addr) ? mem[req.addr] : 32'h0;
      end

      @(negedge clk);
      bus_id = req.id;
      bus_op = req.op;
      bus_addr = req.addr;
      bus_data = read_data;
      bus_valid = 1;

      @(posedge clk);

      rsp = new();
      rsp.id = req.id;
      rsp.ok = 1'b1;
      rsp.data = read_data;
      svx_put_M7BusRsp("m7.bus.rsp", rsp);

      @(negedge clk);
      bus_valid = 0;
    end
  endtask

  task automatic existing_style_monitor();
    M7BusObs obs;
    int seen = 0;

    while (seen < NUM_TX) begin
      @(posedge clk);
      if (bus_valid) begin
        obs = new();
        obs.id = bus_id;
        obs.op = bus_op;
        obs.addr = bus_addr;
        obs.data = bus_data;
        svx_put_M7BusObs("m7.bus.mon", obs);
        seen++;
      end
    end
  endtask

  initial begin
    bus_valid = 0;
    bus_id = 0;
    bus_op = M7_OP_READ;
    bus_addr = 0;
    bus_data = 0;

    $display("M7 SV typed helper test start @ %0.3f ns", $realtime);

    svx_init();

    fork
      begin
        svx_run_test("examples.milestone_7_sv_typed_helpers.tests.smoke_test", "test_smoke");
      end
      begin
        existing_style_driver();
      end
      begin
        existing_style_monitor();
      end
    join

    $display("M7 SV typed helper test done @ %0.3f ns", $realtime);
    $finish;
  end
endmodule
