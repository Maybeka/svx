`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/milestone_6_cli_workflow/generated/types.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  localparam int NUM_TX = 2;

  bit clk;
  bit bus_valid;
  M6BusOp bus_op;
  int bus_id;
  bit [7:0] bus_addr;
  bit [31:0] bus_data;
  bit [31:0] mem [int unsigned];

  initial begin
    clk = 0;
    forever #(0.5ns) clk = ~clk;
  end

  task automatic get_req(output M6BusReq req);
    svx_get_M6BusReq("m6.bus.req", req);
  endtask

  task automatic put_rsp(input M6BusRsp rsp);
    svx_put_M6BusRsp("m6.bus.rsp", rsp);
  endtask

  task automatic put_obs(input M6BusObs obs);
    svx_put_M6BusObs("m6.bus.mon", obs);
  endtask

  task automatic existing_style_driver();
    M6BusReq req;
    M6BusRsp rsp;
    bit [31:0] read_data;

    for (int i = 0; i < NUM_TX; i++) begin
      get_req(req);

      if (req.op == M6_OP_WRITE) begin
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
      put_rsp(rsp);

      @(negedge clk);
      bus_valid = 0;
    end
  endtask

  task automatic existing_style_monitor();
    M6BusObs obs;
    int seen = 0;

    while (seen < NUM_TX) begin
      @(posedge clk);
      if (bus_valid) begin
        obs = new();
        obs.id = bus_id;
        obs.op = bus_op;
        obs.addr = bus_addr;
        obs.data = bus_data;
        put_obs(obs);
        seen++;
      end
    end
  endtask

  initial begin
    bus_valid = 0;
    bus_id = 0;
    bus_op = M6_OP_READ;
    bus_addr = 0;
    bus_data = 0;

    $display("M6 CLI workflow test start @ %0.3f ns", $realtime);

    svx_init();

    fork
      begin
        svx_run_test("examples.milestone_6_cli_workflow.tests.smoke_test", "test_smoke");
      end
      begin
        existing_style_driver();
      end
      begin
        existing_style_monitor();
      end
    join

    $display("M6 CLI workflow test done @ %0.3f ns", $realtime);
    $finish;
  end
endmodule
