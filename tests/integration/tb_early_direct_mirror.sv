`include "sv/svx_pkg.sv"
`include ".tmp/early_constructor/common.svh"
`include ".tmp/early_constructor/source.sv"
module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.same_package_test");
    svx_start("same_package.direct");
    if (same_package_pkg::A::allocations != 1 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "direct mirror construction leaked a receiver");
    svx_shutdown();
    $display("EARLY_DIRECT_MIRROR_PASS");
    $finish;
  end
endmodule
