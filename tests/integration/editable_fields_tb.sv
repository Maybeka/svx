// SPDX-License-Identifier: Apache-2.0
module editable_fields_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.editable_fields_entry");
    svx_start("editable_fields.run");
    svx_shutdown();
    $display("EDITABLE_FIELDS_SV_PASS");
    $finish;
  end
endmodule
