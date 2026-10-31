// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_pkg.sv"
`include "examples/sv_scoped/generated/mirrors.sv"
module tb_sv_scoped;
  timeunit 1ns;
  timeprecision 1ps;
  import svx_pkg::*;
  initial begin
    scoped_base_pkg::Base child;
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("examples.sv_scoped.entry");
    svx_start("sv_scoped.run");
    `SVX_GET_OBJECT(scoped_base_pkg::Base, "scoped.child", child)
    if (child.status()!=121) $fatal(1, "nested Python virtual callback failed");
    if ($time!=2ns) $fatal(1, "nested native task timing changed");
    svx_shutdown();
    $display("SCOPED_SV_PASS");
    $finish;
  end
endmodule
