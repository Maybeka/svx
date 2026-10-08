`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.disable_finally_error_test");
    fork
      begin : disabled_call
        svx_start("disable-finally-error.run");
      end
      begin
        #10ns;
        disable disabled_call;
      end
    join
    #1ns;
    svx_shutdown();
    $fatal(1, "disabled callback swallowed an ordinary exception");
  end
endmodule
