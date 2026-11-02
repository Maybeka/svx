// SPDX-License-Identifier: Apache-2.0
module struct_kinds_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.struct_kinds_entry");
    svx_start("struct_kinds.run");
    svx_shutdown();
    $display("STRUCT_KINDS_SV_PASS");
    $finish;
  end
endmodule
