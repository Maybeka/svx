`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  initial begin
    svx_init();
    svx_load("tests.integration.disable_external_test");
    fork
      begin : disabled_call
        svx_start("disable_external.run");
      end
      begin
        #10ns;
        disable disabled_call;
      end
    join
    #1ns;
    $display("SVX_EXTERNAL_DISABLE_PASS");
    $finish;
  end
endmodule
