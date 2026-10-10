`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/register_lab/generated/models.sv"
`include "examples/register_lab/register_if.sv"
`include "examples/register_lab/dut.sv"
`include "examples/register_lab/policy_types.sv"
`include "examples/register_lab/generated/inheritance.sv"
`include "examples/register_lab/checker.sv"
`include "examples/register_lab/generated/report.sv"
`ifdef REGISTER_LAB_UVMX
  `include "incubator/uvmx/sv/uvmx_pkg.sv"
  `include "incubator/uvmx/examples/register_lab/legacy_test.sv"
  `include "incubator/uvmx/examples/register_lab/generated/tests.sv"
`endif

module tb;
  timeunit 1ns;
  timeprecision 1ps;
  import svx_pkg::*;
  register_policy_pkg::RegisterPolicy policy;

  bit clk = 0;
  bit reset_n = 0;
  logic [7:0] debug_status = 8'b10xz01z0;
  register_if bus(clk);
  register_bank dut(clk, reset_n, bus.valid, bus.write, bus.address, bus.wdata, bus.rdata);

  always #0.5ns clk = ~clk;

  initial begin
    repeat (2) @(negedge clk);
    reset_n = 1;
  end

  task automatic notify_done(string role);
    byte unsigned bytes[$];
    for (int i = 0; i < role.len(); i++) bytes.push_back(role.getc(i));
    svx_channel_put_byte_queue("lab.env.done", bytes);
  endtask

  task automatic driver();
    RegisterRequest request;
    RegisterResponse response;
    wait (reset_n);
    repeat (8) begin
      svx_get_RegisterRequest("lab.bus.req", request);
      @(negedge clk);
      bus.tag = request.tag;
      bus.write = request.write;
      bus.address = request.address;
      bus.wdata = request.data;
      bus.valid = 1;
      @(posedge clk);
      #1ps;
      response = new();
      response.tag = request.tag;
      response.data = bus.write ? bus.wdata : bus.rdata;
      response.data = policy.normalize(response.data);
      svx_put_RegisterResponse("lab.bus.rsp", response);
      @(negedge clk);
      bus.valid = 0;
    end
    notify_done("driver");
  endtask

  task automatic monitor();
    RegisterObservation observation;
    int seen = 0;
    wait (reset_n);
    while (seen < 8) begin
      @(posedge clk);
      if (bus.valid) begin
        observation = new();
        observation.tag = bus.tag;
        observation.write = bus.write;
        observation.address = bus.address;
        observation.data = bus.write ? bus.wdata : bus.rdata;
        svx_put_RegisterObservation("lab.bus.mon", observation);
        seen++;
      end
    end
    notify_done("monitor");
  endtask

  task automatic trace_echo();
    byte unsigned trace_bytes[$];
    chandle payload;
    svx_channel_get_payload("lab.trace.req", payload);
    svx_payload_to_byte_queue(payload, trace_bytes);
    svx_payload_destroy(payload);
    svx_channel_put_byte_queue("lab.trace.rsp", trace_bytes);
    notify_done("trace");
  endtask

  initial begin
    string selected;
    svx_proxy_extensions::CheckerFactory#(RegisterChecker) checker_factory;
    register_report_pkg::Report report;
    int observed, budget, result;
    bus.valid = 0;
    if (!$value$plusargs("LAB_CASE=%s", selected)) selected = "smoke";
    svx_init_with_signal_declarations("examples.register_lab.signals");
    checker_factory = new();
    svx_load("examples.register_lab.extensions");
    svx_load("examples.register_lab.reporting");
    svx_start("register_lab.register_report");
    report = new();
    svx_start("register_lab.create_policy");
    `SVX_GET_OBJECT(register_policy_pkg::RegisterPolicy, "register_lab.policy", policy)
    policy.bus = bus;
    budget = 4;
    result = policy.calibrate(2, observed, budget);
    if (result != 9 || observed != 3 || budget != 8)
      $fatal(2, "REGISTER_LAB_DIRECTION_COPYOUT_FAILED");
    $display("REGISTER_LAB_SV_CALLBACK_PASS");
    fork
`ifdef REGISTER_LAB_UVMX
      uvmx_pkg::uvmx_run_test("incubator.uvmx.examples.register_lab.python_test");
`else
      svx_run_test("examples.register_lab.scenarios", selected);
`endif
      driver();
      monitor();
      trace_echo();
    join
    report.completed();
    report.settle();
    svx_shutdown();
    $display("REGISTER_LAB_PASS case=%s", selected);
    $finish;
  end

  initial begin
    #200ns;
    $fatal(2, "REGISTER_LAB_TIMEOUT");
  end
endmodule
