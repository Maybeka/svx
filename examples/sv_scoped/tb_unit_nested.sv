// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
`include "examples/sv_scoped/unit_nested.sv"

module tb_unit_nested;
  import svx_pkg::*;
  svx_exports exports();
  initial begin
    Outer::Inner driver;
    svx_init();
    exports.initialize();
    svx_load("examples.sv_scoped.unit_nested");
    svx_start("unit_nested.run");
    `SVX_GET_OBJECT(Outer::Inner, "unit.nested", driver)
    if (driver.status() != 108) $fatal(1, "nested unit virtual callback");
    if ($time != 2) $fatal(1, "nested unit task timing");
    svx_shutdown();
    $display("UNIT_NESTED_NATIVE_PASS");
    $finish;
  end
endmodule
