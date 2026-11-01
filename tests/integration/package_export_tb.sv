`timescale 1ns/1ps
`include "sv/svx_defs.svh"
module package_export_tb;
  import svx_pkg::*;
  export_base_pkg::Base base_handle;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("package_export_inheritance");
    svx_start("package_export.run");
    `SVX_GET_OBJECT(export_base_pkg::Base, "package_driver", base_handle)
    if (base_handle.status() != 125) $fatal(1, "virtual callback");
    if (base_handle.identity() != 10) $fatal(1, "nonvirtual base dispatch");
    if (export_base_pkg::base_constructions != 1 ||
        export_driver_pkg::driver_constructions != 1) $fatal(1, "duplicate construction");
    if ($time != 1) $fatal(1, "task timing");
    $display("PACKAGE_EXPORT_NATIVE_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
