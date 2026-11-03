// SPDX-License-Identifier: Apache-2.0
module inline_parameter_handles_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.inline_parameter_handles_entry");
    svx_start("inline_handles.run");
    svx_shutdown();
    $display("INLINE_HANDLES_SV_PASS");
    $finish;
  end
endmodule
