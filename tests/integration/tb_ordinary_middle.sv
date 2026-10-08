`define SV_ROOT_DECLARATIONS_ONLY
`define SV_ROOT_ORDINARY_MIDDLE
`include "tests/integration/tb_sv_root_target.sv"

module tb;
  import svx_pkg::*;
  sv_root_pkg::A base_handle;
  sv_root_child_pkg::C python_c;
  svx_mirror_sv_sv_root_child_pkg_C::C sv_c;
  initial begin
    svx_init();
    svx_load("tests.integration.ordinary_middle_test");
    svx_start("ordinary_middle.static");
    if ($time != 1)
      $fatal(1, "inherited static task failed to advance time");
    if (sv_root_middle_pkg::Middle::allocations != 0 || svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "static gateway unexpectedly allocated a source receiver");
    svx_start("ordinary_middle.create");
    `SVX_GET_OBJECT(sv_root_child_pkg::C, "ordinary_middle.c", python_c)
    base_handle = python_c;
    if (python_c.middle != 310 || base_handle.check() != 445)
      $fatal(1, "ordinary middle Python field/virtual dispatch failed");
    python_c.middle = 320;
    svx_start("ordinary_middle.close");
    sv_c = new();
    base_handle = sv_c;
    if (sv_c.middle != 300 || base_handle.check() != 435)
      $fatal(1, "ordinary middle SV-origin construction failed");
    svx_start("ordinary_middle.verify_sv");
    if (sv_root_middle_pkg::Middle::allocations != 2)
      $fatal(1, "ordinary middle receiver allocation count mismatch");
    svx_start("ordinary_middle.static_after_close");
    if ($time != 2 || sv_root_middle_pkg::Middle::allocations != 2)
      $fatal(1, "static dispatch after close created a receiver or lost timing");
    if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0)
      $fatal(1, "ordinary middle receiver/context leaked");
    svx_shutdown();
    $display("ORDINARY_MIDDLE_PASS");
    $finish;
  end
endmodule
