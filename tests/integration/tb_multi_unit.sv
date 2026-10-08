`include "sv/svx_pkg.sv"
`include ".tmp/multi_unit/common.svh"
`include ".tmp/multi_unit/source.sv"
module tb;
  import svx_pkg::*;
  multi_a_pkg::A base_handle;
  multi_c_pkg::C python_d;
  multi_e_pkg::E python_e;
  svx_mirror_sv_multi_e_pkg_E::E sv_e;
  initial begin
    svx_init();
    svx_load("tests.integration.multi_unit_test");
    svx_start("multi_unit.types");
    sv_e = new(); base_handle = sv_e;
    if (base_handle.check() != 1535) $fatal(1, "multi-input SV-origin dispatch failed");
    svx_start("multi_unit.verify_sv");
    svx_start("multi_unit.create");
    `SVX_GET_OBJECT(multi_c_pkg::C, "multi_unit.d", python_d)
    `SVX_GET_OBJECT(multi_e_pkg::E, "multi_unit.e", python_e)
    base_handle = python_d;
    if (base_handle.check() != 1035) $fatal(1, "multi-input Python D dispatch failed");
    base_handle = python_e;
    if (base_handle.check() != 1535) $fatal(1, "multi-input Python E dispatch failed");
    svx_start("multi_unit.close");
    if (multi_a_pkg::A::allocations != 3 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "multi-input allocation/registry/context mismatch");
    svx_shutdown();
    $display("MULTI_UNIT_PASS");
    $finish;
  end
endmodule
