`include "sv/svx_pkg.sv"
`include ".tmp/python_multi_unit/common.svh"
`include ".tmp/python_multi_unit/source.sv"
module tb;
  import svx_pkg::*;
  svx_proxy_python_unit_source::Root base_handle;
  svx_mirror_sv_python_multi_final_pkg_Grandchild::Grandchild sv_final;
  python_unit_pkg::Child python_derived;
  python_multi_final_pkg::Grandchild python_final;
  initial begin
    svx_init();
    svx_load("tests.integration.python_multi_unit_test");
    svx_start("python_multi_unit.types");
    if ($test$plusargs("MULTI_SUPER_MISMATCH")) svx_start("python_multi_unit.mismatch");
    sv_final = new(19); base_handle = sv_final;
    if (base_handle.check(1) != 1620) $fatal(1, "multi-input SV-origin virtual failed");
    svx_start("python_multi_unit.verify_sv");
    svx_start("python_multi_unit.rollback");
    if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0)
      $fatal(1, "multi-input rollback registry/context leaked");
    svx_start("python_multi_unit.create");
    `SVX_GET_OBJECT(python_unit_pkg::Child, "python_multi_unit.derived", python_derived)
    `SVX_GET_OBJECT(python_multi_final_pkg::Grandchild, "python_multi_unit.final", python_final)
    base_handle = python_derived;
    if (base_handle.check(1) != 1124) $fatal(1, "multi-input Python Derived virtual failed");
    base_handle = python_final;
    if (base_handle.check(1) != 1632) $fatal(1, "multi-input Python final virtual failed");
    svx_start("python_multi_unit.close");
    if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0)
      $fatal(1, "multi-input registry/context leaked");
    svx_shutdown();
    $display("PYTHON_MULTI_UNIT_PASS");
    $finish;
  end
endmodule
