`include "tests/integration/signature_types.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/signature_types/mirrors.sv"

class Unrelated;
endclass

module tb;
  import svx_pkg::*;
  initial begin
    signature_types_pkg::Base#(int, 8) callback_target;
    svx_dispatchable broad_target;
    svx_mirror_sv_signature_types_pkg_Hosted::Hosted hosted;
    svx_mirror_sv_signature_types_pkg_Hosted::Hosted wrapped, failed_owned;
    int result;
    svx_init();
    svx_load("tests.integration.signature_types_test");
    svx_start("signature_types.run");
    if ($test$plusargs("SVX_HANDOFF_TYPE_NEGATIVE")) begin
      `SVX_GET_OBJECT(Unrelated, "signature_types.close_function", broad_target)
      $fatal(1, "wrong expected type unexpectedly accepted");
    end
    if ($test$plusargs("SVX_CLOSE_FUNCTION") || $test$plusargs("SVX_CLEANUP_WAIT_NEGATIVE")) begin
      `SVX_GET_OBJECT(signature_types_pkg::Base#(int, 8), "signature_types.close_function", callback_target)
      result = callback_target.check(8'h05);
      if ($test$plusargs("SVX_CLEANUP_WAIT_NEGATIVE"))
        $fatal(1, "cleanup wait unexpectedly returned %0d", result);
      if (result != 9 || $time != 0) $fatal(1, "function close failed");
      $display("SIGNATURE_TYPES_FUNCTION_CLOSE_PASS");
    end
    hosted = new(20);
    if (hosted.count != 21 || hosted.check(8'h05) != 26)
      $fatal(1, "SV-origin field initialization or callback failed");
    svx_start("signature_types.verify_hosted");
    if (hosted.count != 21) $fatal(1, "closing Python view damaged the SV object");
    wrapped = new(30, 100001);
    failed_owned = new(40, 100002);
    svx_start("signature_types.wrap_existing");
    if (wrapped.count != 31 || failed_owned.count != 42)
      $fatal(1, "existing-object wrapping created or destroyed the wrong SV object");
    svx_shutdown();
    $display("SIGNATURE_TYPES_PASS");
    $finish;
  end
endmodule
