// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_pkg.sv"
`include "examples/sv_export/generated/mirrors.sv"

module tb_package_calls;
  timeunit 1ns;
  timeprecision 1ps;
  import svx_pkg::*;
  export_status_if status_bus();
  initial begin
    status_bus.ready=1;
    export_driver_pkg::observed_bus=status_bus;
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("examples.sv_export.package_calls");
    svx_start("sv_export.package_calls");
    if ($time != 3ns) $fatal(1, "package task did not consume native simulation time");
    if (export_driver_pkg::package_counter != 5) $fatal(1, "wrong package state");
    svx_shutdown();
    $display("PACKAGE_CALLS_SV_PASS");
    $finish;
  end
endmodule
