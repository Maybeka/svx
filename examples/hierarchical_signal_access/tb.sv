`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  reg ready;
  reg [7:0] data;
  logic [7:0] status;

  initial begin
    ready = 0;
    data = 0;
    status = 8'b10xz01z0;
    svx_init_with_signal_declarations(
      "examples.hierarchical_signal_access.signal_declarations"
    );
    svx_run_test(
      "examples.hierarchical_signal_access.signal_test",
      "test_signal_access"
    );
    svx_shutdown();
    $finish;
  end
endmodule
