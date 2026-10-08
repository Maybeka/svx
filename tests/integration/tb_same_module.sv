`include "sv/svx_pkg.sv"
`include ".tmp/same_package/common.svh"
`include ".tmp/same_package/source.sv"
module tb;
  import svx_pkg::*;
  same_package_pkg::A base_handle;
  same_package_pkg::C python_d;
  same_package_pkg::E python_e;
  svx_mirror_sv_same_package_pkg_E::E sv_e;
  initial begin
    svx_init();
    svx_load("tests.integration.same_module_test");
    svx_start("same_module.types");
    sv_e = new();
    base_handle = sv_e;
    if (base_handle.check() != 1535)
      $fatal(1, "shared-module SV-first virtual dispatch failed");
    svx_start("same_module.verify_sv");
    svx_start("same_module.create");
    `SVX_GET_OBJECT(same_package_pkg::C, "same_module.d", python_d)
    `SVX_GET_OBJECT(same_package_pkg::E, "same_module.e", python_e)
    base_handle = python_d;
    if (base_handle.check() != 1035)
      $fatal(1, "shared-module Python D virtual dispatch failed");
    base_handle = python_e;
    if (base_handle.check() != 1535)
      $fatal(1, "shared-module Python E virtual dispatch failed");
    svx_start("same_module.close");
    if (same_package_pkg::A::allocations != 3 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "shared-module allocation/registry/context mismatch");
    svx_shutdown();
    $display("SAME_MODULE_STARTUP_PASS");
    $finish;
  end
endmodule
