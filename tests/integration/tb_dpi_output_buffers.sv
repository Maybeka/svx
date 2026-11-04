`include "tests/integration/dpi_output_buffers.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/dpi-output-capacity/export/mirrors.sv"
module tb;
  initial begin
    svx_pkg::svx_init();
    svx_exports_pkg::initialize();
    svx_pkg::svx_load("tests.integration.dpi_output_buffers_test");
    svx_pkg::svx_start("dpi_output_buffers.run");
    svx_pkg::svx_shutdown();
    $display("DPI_OUTPUT_BUFFERS_SV_PASS");
    $finish;
  end
endmodule
