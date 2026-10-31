// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
module tb_independent_units;
  import svx_pkg::*;
  base_unit_probe first();
  child_unit_probe second();
  initial begin
    unit_child_pkg::Child child;
    if (unit_base_pkg::WIDTH != 5 || unit_child_pkg::WIDTH != 13)
      $fatal(1, "compilation-unit macro state changed");
    if (first.read_local() != 11 || second.read_local() != 22)
      $fatal(1, "independent unit class identity changed");
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("examples.sv_export.unit_entry");
    svx_start("sv_export.independent_units");
    `SVX_GET_OBJECT(unit_child_pkg::Child, "export.units.child", child)
    if (unit_child_pkg::consume(child) != 109)
      $fatal(1, "SV virtual call did not reach Python");
    if ($time != 2) $fatal(1, "timed call did not advance simulation");
    svx_shutdown();
    $display("INDEPENDENT_UNITS_SV_PASS");
    $finish;
  end
endmodule
