`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  reg flag;
  reg [7:0] data;
  logic [7:0] logic_data;

  initial begin
    flag = 0;
    data = 0;
    logic_data = 8'b10xz01z0;
    svx_init_with_signal_declarations("tests.integration.m14_signal_declarations");
    svx_run_test("tests.integration.m14_signal_test", "test_signal_access");
    svx_shutdown();
    $finish;
  end
endmodule
