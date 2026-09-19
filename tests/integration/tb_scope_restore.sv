`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  import "DPI-C" context task svx_scope_restore_probe(output int result);

  initial begin
    int result;
    svx_scope_restore_probe(result);
    if (result != 1) begin
      $fatal(2, "SVX did not restore the caller DPI scope");
    end
    $display("SVX_SCOPE_RESTORE_PASS");
    $finish;
  end
endmodule
