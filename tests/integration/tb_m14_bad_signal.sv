`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;

  initial begin
    svx_init_with_signal_declarations("tests.integration.m14_bad_signal_declarations");
    $fatal(2, "M14 invalid declarations unexpectedly succeeded");
  end
endmodule
