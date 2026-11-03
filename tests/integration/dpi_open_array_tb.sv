// SPDX-License-Identifier: Apache-2.0
module dpi_open_array_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.dpi_open_array_entry");
    svx_start("dpi_open_array.run");
    svx_shutdown();
    $display("DPI_OPEN_ARRAY_SV_PASS");
    $finish;
  end
endmodule
