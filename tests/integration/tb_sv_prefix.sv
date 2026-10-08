`define SV_ROOT_DECLARATIONS_ONLY
`define SV_ROOT_PREFIX
`include "tests/integration/tb_sv_root_target.sv"

module tb;
  import svx_pkg::*;
  sv_root_prefix_pkg::Z base_handle;
  sv_root_child_pkg::C python_c;
  svx_mirror_sv_sv_root_child_pkg_C::C sv_c;
  initial begin
    svx_init();
    svx_load("tests.integration.sv_prefix_test");
    if (sv_root_prefix_pkg::Z::allocations != 0)
      $fatal(1, "prefix static gateway allocated a receiver");
    svx_start("sv_prefix.direct");
    svx_start("sv_prefix.create");
    `SVX_GET_OBJECT(sv_root_child_pkg::C, "sv_prefix.c", python_c)
    base_handle = python_c;
    if (base_handle.prefix_count != 410 || base_handle.prefix_virtual() != 433)
      $fatal(1, "prefix Python-origin field/virtual dispatch failed");
    base_handle.prefix_count = 420;
    svx_start("sv_prefix.close");
    sv_c = new();
    base_handle = sv_c;
    if (base_handle.prefix_count != 400 || base_handle.prefix_virtual() != 423)
      $fatal(1, "prefix SV-origin field/virtual dispatch failed");
    svx_start("sv_prefix.verify_sv");
    if (sv_root_prefix_pkg::Z::allocations != 4 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "prefix source allocation/receiver/context mismatch");
    svx_shutdown();
    $display("SV_PREFIX_PASS");
    $finish;
  end
endmodule
