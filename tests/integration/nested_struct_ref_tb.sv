// SPDX-License-Identifier: Apache-2.0
module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.nested_struct_ref_entry");
    svx_start("nested_struct_ref.run");
    svx_shutdown();
    $display("NESTED_STRUCT_REF_SV_PASS");
    $finish;
  end
endmodule
