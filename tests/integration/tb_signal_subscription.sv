`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  reg flag = 0;
  reg [31:0] data = 32'h12345678;
  wire [31:0] constant_data = 32'h13579bdf;
  logic [64:0] wide;
  logic [127:0] huge = 'z;
  logic [7:0] driver = 8'h5a;
  wire [7:0] observed = driver;
  logic scalar;
  int signed signed_data = -42;

  initial begin
    #1;
    svx_init_with_signal_declarations("tests.integration.signal_subscription_declarations");
    svx_run_test("tests.integration.signal_subscription_test", "setup");
    data = 32'h87654321;
    svx_run_test("tests.integration.signal_subscription_test", "immediate");
    flag <= 1;
    wide <= {1'b1, {16{4'bxz10}}};
    huge <= {32{4'bzx01}};
    #1;
    svx_run_test("tests.integration.signal_subscription_test", "settled");
    data = 'x;
    #1;
    svx_run_test("tests.integration.signal_subscription_test", "unknown_two_state");
    data = 32'h87654321;
    #1;
    svx_run_test("tests.integration.signal_subscription_test", "exercise");
    svx_shutdown();
    data = 99;
    #1;
    $display("SIGNAL_SUBSCRIPTION_SHUTDOWN_PASS");
    $finish;
  end
endmodule
