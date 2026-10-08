`define SV_ROOT_DECLARATIONS_ONLY
`define SV_ROOT_INHERITED_SLOT
`define SV_ROOT_EXTENDED
`include "tests/integration/tb_sv_root_target.sv"

module tb;
  import svx_pkg::*;
  sv_root_pkg::A handle;
  svx_mirror_sv_sv_root_e_pkg_E::E sv_e;
  initial begin
    svx_init();
    svx_load("tests.integration.inherited_virtual_slot_test");
    svx_start("inherited_virtual_slot.create");
    `SVX_GET_OBJECT(sv_root_pkg::A, "inherited_virtual_slot.d", handle)
    if (handle.check() != 1035)
      $fatal(1, "inherited A virtual slot did not reach D override");
    handle.count = 19;
    if (handle.check() != 1042)
      $fatal(1, "inherited slot did not preserve live receiver/super dispatch");
    svx_start("inherited_virtual_slot.close");
    svx_start("inherited_virtual_slot.create_e");
    `SVX_GET_OBJECT(sv_root_pkg::A, "inherited_virtual_slot.e", handle)
    if (handle.check() != 1535)
      $fatal(1, "E did not preserve inherited callback boundary for D");
    handle.count = 19;
    svx_start("inherited_virtual_slot.close_e");
    sv_e = new();
    handle = sv_e;
    if (handle.check() != 1535)
      $fatal(1, "SV-origin E lost inherited virtual slot");
    svx_start("inherited_virtual_slot.close_sv_e");
    if (svx_construction_context::frames.size() != 0)
      $fatal(1, "inherited slot constructor leaked context");
    svx_shutdown();
    $display("INHERITED_VIRTUAL_SLOT_PASS");
    $finish;
  end
endmodule
