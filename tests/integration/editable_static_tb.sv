`timescale 1ns/1ps
module editable_static_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.editable_static_entry");
    svx_start("editable_static.run");
    if ($time != 2ns) $fatal(1, "static task timing changed");
    $display("EDITABLE_STATIC_SV_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
