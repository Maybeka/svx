`include "sv/svx_pkg.sv"

module tb;
  initial begin
    svx_pkg::svx_runtime_init(
      svx_pkg::SVX_SV_RUNTIME_ABI_VERSION,
      "9.9.9"
    );
    $fatal(2, "SVX runtime accepted a mismatched SystemVerilog product version");
  end
endmodule
