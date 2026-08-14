`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/milestone_5_existing_env/generated_types.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  bit clk;
  bit bus_valid;
  M5BusOp bus_op;
  int bus_id;
  bit [7:0] bus_addr;
  bit [31:0] bus_data;
  bit [31:0] mem [int unsigned];
  int num_tx;
  string python_entry;

  initial begin
    clk = 0;
    forever #(0.5ns) clk = ~clk;
  end

  task automatic get_req(output M5BusReq req);
    svx_get_M5BusReq("env.bus0.req", req);
  endtask

  task automatic put_rsp(input M5BusRsp rsp);
    svx_put_M5BusRsp("env.bus0.rsp", rsp);
  endtask

  task automatic put_obs(input M5BusObs obs);
    svx_put_M5BusObs("env.bus0.mon", obs);
  endtask

  task automatic existing_style_driver();
    M5BusReq req;
    M5BusRsp rsp;
    bit [31:0] read_data;

    for (int i = 0; i < num_tx; i++) begin
      get_req(req);

      if (req.op == M5_OP_WRITE) begin
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
    M5BusObs obs;
    int seen = 0;

    while (seen < num_tx) begin
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
    bus_op = M5_OP_READ;
    bus_addr = 0;
    bus_data = 0;
    num_tx = 4;
    python_entry = "examples.milestone_5_existing_env.tests.integration_test.python_controlled_test";

    if ($test$plusargs("SVX_M5_CHECKER_FAILURE")) begin
      num_tx = 1;
      python_entry = "examples.milestone_5_existing_env.tests.integration_test.python_checker_failure_demo";
    end

    $display("M5 existing-environment integration test start @ %0.3f ns", $realtime);

    svx_init();
    svx_load("examples.milestone_5_existing_env.tests.integration_test");

    fork
      begin
        svx_start(python_entry);
      end
      begin
        existing_style_driver();
      end
      begin
        existing_style_monitor();
      end
    join

    $display("M5 existing-environment integration test done @ %0.3f ns", $realtime);
    $finish;
  end
endmodule
