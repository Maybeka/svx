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

  function automatic void require_svtypes_payload(chandle payload, string channel_name, string expected_type);
    if (svx_payload_kind(payload) != "svtypes") begin
      $fatal(2, "%s expected svtypes payload, got kind %s", channel_name, svx_payload_kind(payload));
    end
    if (svx_payload_type_name(payload) != expected_type) begin
      $fatal(2, "%s expected type %s, got %s", channel_name, expected_type, svx_payload_type_name(payload));
    end
    if (svx_payload_content_type(payload) != "application/x-svtypes") begin
      $fatal(2, "%s expected SvTypes content type, got %s", channel_name, svx_payload_content_type(payload));
    end
  endfunction

  task automatic get_req(output M6BusReq req);
    chandle payload;
    byte unsigned bytes[$];
    int offset;

    svx_channel_get_payload("m6.bus.req", payload);
    require_svtypes_payload(payload, "m6.bus.req", "M6BusReq");
    svx_payload_to_byte_queue(payload, bytes);
    svx_payload_destroy(payload);

    req = new();
    offset = 0;
    req.unpack(bytes, offset);
    if (offset != bytes.size()) begin
      $fatal(2, "m6.bus.req unpack offset=%0d size=%0d", offset, bytes.size());
    end
  endtask

  task automatic put_rsp(input M6BusRsp rsp);
    byte unsigned bytes[$];
    rsp.pack(bytes);
    svx_channel_put_byte_queue("m6.bus.rsp", bytes, "svtypes", "M6BusRsp", "application/x-svtypes");
  endtask

  task automatic put_obs(input M6BusObs obs);
    byte unsigned bytes[$];
    obs.pack(bytes);
    svx_channel_put_byte_queue("m6.bus.mon", bytes, "svtypes", "M6BusObs", "application/x-svtypes");
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
