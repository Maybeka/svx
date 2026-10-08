`include "sv/svx_pkg.sv"
`include ".tmp/python_unit/common.svh"
`include ".tmp/python_unit/source.sv"
module tb;
  import svx_pkg::*;
  svx_proxy_python_unit_source::Root base_handle;
  svx_mirror_sv_python_unit_pkg_Grandchild::Grandchild sv_final;
  python_unit_pkg::Child python_derived;
  python_unit_pkg::Grandchild python_final;
  initial begin
    svx_init();
    svx_load("tests.integration.python_unit_test");
    svx_start("python_unit.types");
    if ($test$plusargs("UNIT_SUPER_MISMATCH")) svx_start("python_unit.mismatch");
    if (svx_proxy_python_unit_source::Root::scale(7) != 21)
      $fatal(1, "source-unit root static dispatch failed");
    sv_final = new(19);
    base_handle = sv_final;
    if (base_handle.check(1) != 1620)
      $fatal(1, "source-unit SV-origin virtual dispatch failed");
    svx_start("python_unit.verify_sv");
    svx_start("python_unit.create");
    `SVX_GET_OBJECT(python_unit_pkg::Child, "python_unit.derived", python_derived)
    `SVX_GET_OBJECT(python_unit_pkg::Grandchild, "python_unit.final", python_final)
    base_handle = python_derived;
    if (base_handle.check(1) != 1124)
      $fatal(1, "source-unit Python Derived dispatch failed");
    base_handle = python_final;
    if (base_handle.check(1) != 1632)
      $fatal(1, "source-unit Python Grandchild dispatch failed");
    svx_start("python_unit.close");
    if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0)
      $fatal(1, "source-unit receiver or constructor context leaked");
    svx_shutdown();
    $display("PYTHON_UNIT_PASS");
    $finish;
  end
endmodule
