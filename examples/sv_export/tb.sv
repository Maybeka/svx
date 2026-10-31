// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_pkg.sv"
`include "examples/sv_export/generated/mirrors.sv"

module tb_sv_export;
  import svx_pkg::*;
  initial begin
    export_base_pkg::Base driver;
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("examples.sv_export.entry");
    svx_start("sv_export.run");
    `SVX_GET_OBJECT(export_base_pkg::Base, "export.driver", driver)
    if (driver.status() != 108) $fatal(1, "virtual callback did not reach Python");
    svx_shutdown();
    $display("SV_EXPORT_SV_PASS");
    $finish;
  end
endmodule
