`include "sv/svx_pkg.sv"
`include ".tmp/same_package/common.svh"
`include ".tmp/same_package/source.sv"

module tb;
  import svx_pkg::*;
  same_package_pkg::A base_handle;
  same_package_pkg::C python_c;
  svx_mirror_sv_same_package_pkg_C::C sv_c;
  initial begin
    svx_init();
    svx_load("tests.integration.same_package_test");
`ifdef SVX_INCLUDE_LOCATION_CHECK
    if (same_package_pkg::A::declaration_file != "tests/integration/same_package_include_base.svh"
        || same_package_pkg::A::declaration_line != 4
        || same_package_pkg::C::declaration_file != "tests/integration/same_package_include_derived.svh"
        || same_package_pkg::C::declaration_line != 3)
      $fatal(1, "included declaration file/line macros changed");
    $display("SAME_PACKAGE_INCLUDE_LOCATIONS_PASS");
`endif
`ifdef SVX_DIRECT_LOCATION_CHECK
    if (same_package_pkg::C::declaration_file != "tests/integration/same_package_source.sv"
        || same_package_pkg::C::declaration_line != 20)
      $fatal(1, "direct source declaration file/line macros changed");
    $display("SAME_PACKAGE_DIRECT_LOCATIONS_PASS");
`endif
    if (same_package_pkg::A::allocations != 0)
      $fatal(1, "inline static dispatcher allocated a source receiver");
    // Construct from SV before any Python consumer asks for the deferred C view.
    sv_c = new();
    base_handle = sv_c;
    if (base_handle.check() != 135)
      $fatal(1, "same-package SV-origin dispatch failed");
    svx_start("same_package.verify_sv");
    svx_start("same_package.direct");
    svx_start("same_package.create");
    `SVX_GET_OBJECT(same_package_pkg::C, "same_package.c", python_c)
    base_handle = python_c;
    if (base_handle.check() != 142 || python_c.observed != 23)
      $fatal(1, "same-package Python-origin dispatch failed");
    python_c.extra = 110;
    svx_start("same_package.close");
    if (same_package_pkg::A::allocations != 3 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "same-package source allocation/registry/context mismatch");
    svx_shutdown();
    $display("SAME_PACKAGE_PASS");
    $finish;
  end
endmodule
