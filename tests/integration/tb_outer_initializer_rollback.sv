`define SV_ROOT_DECLARATIONS_ONLY
`define SV_ROOT_EXTENDED
`include "tests/integration/tb_sv_root_target.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.outer_initializer_rollback_test");
    svx_start("outer_initializer.run");
    if (svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "failed outer initializer retained SV receiver");
    if (svx_inheritance_registry::published_object_ids.exists("outer_initializer.failed"))
      $fatal(1, "failed outer initializer retained published handle");
    if (svx_construction_context::frames.size() != 0)
      $fatal(1, "failed outer initializer leaked constructor context");
    svx_shutdown();
    $display("OUTER_INITIALIZER_ROLLBACK_PASS");
    $finish;
  end
endmodule
