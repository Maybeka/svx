// SPDX-License-Identifier: Apache-2.0
module dpi_capabilities_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.dpi_capabilities_entry");
    svx_start("dpi_capabilities.run");
    svx_shutdown();
    $display("DPI_CAPABILITIES_SV_PASS");
    $finish;
  end
endmodule
