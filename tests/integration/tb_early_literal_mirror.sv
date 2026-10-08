`include "sv/svx_pkg.sv"
`include ".tmp/early_constructor/common.svh"
`include ".tmp/early_constructor/source.sv"
module tb;
  import svx_pkg::*;
  svx_mirror_sv_same_package_pkg_A::A receiver;
  initial begin
    svx_init();
    svx_load("tests.integration.early_literal_mirror_test");
    svx_start("early_literal.create");
    receiver = new();
    if (receiver.check() != 11) $fatal(1, "SV-origin literal mirror callback mismatch");
    svx_start("early_literal.verify_sv");
    if (same_package_pkg::A::allocations != 2 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "literal mirror construction leaked a receiver");
    svx_shutdown();
    $display("EARLY_LITERAL_MIRROR_PASS");
    $finish;
  end
endmodule
