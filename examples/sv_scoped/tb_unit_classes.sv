// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
`include "examples/sv_scoped/unit_classes.sv"

module tb_unit_classes;
  import svx_pkg::*;
  svx_exports exports();
  initial begin
    Driver driver;
    svx_init();
    exports.initialize();
    svx_load("examples.sv_scoped.unit_classes");
    svx_start("unit_classes.run");
    `SVX_GET_OBJECT(Driver, "unit.driver", driver)
    if (driver.status() != 108) $fatal(1, "unit virtual callback");
    if ($time != 2) $fatal(1, "unit task timing");
    svx_shutdown();
    $display("UNIT_CLASSES_NATIVE_PASS");
    $finish;
  end
endmodule
