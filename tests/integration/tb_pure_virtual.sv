`include "tests/integration/pure_virtual_types.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/pure_virtual/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    pure_virtual_pkg::Base value;
    int result, changed, observed;
    svx_init();
    svx_load("tests.integration.pure_virtual_test");
    svx_start("pure_virtual.run");
    `SVX_GET_OBJECT(pure_virtual_pkg::Base, "pure_virtual.instance", value)
    result = value.check(3);
    if ($test$plusargs("SVX_PURE_FUNCTION_NEGATIVE"))
      $fatal(1, "pure function base unexpectedly returned");
    if (result != 10 || $time != 0) $fatal(1, "pure function override failed");
    $display("PURE_VIRTUAL_FUNCTION_OVERRIDE_PASS");
    changed = 11;
    observed = -1;
    value.update(5, changed, observed);
    if ($test$plusargs("SVX_PURE_TASK_NEGATIVE"))
      $fatal(1, "pure task base unexpectedly returned");
    if (changed != 16 || observed != 32 || $time != 2)
      $fatal(1, "pure task override/copyout failed");
    $display("PURE_VIRTUAL_TASK_OVERRIDE_PASS");
    svx_start("pure_virtual.close");
    svx_shutdown();
    $display("PURE_VIRTUAL_PASS");
    $finish;
  end
endmodule
