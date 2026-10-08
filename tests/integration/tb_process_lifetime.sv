`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.process_lifetime_test");
    svx_start("process_lifetime.run");
    svx_shutdown();
    if ($time != 202) $fatal(1, "shutdown did not cancel the active delay");
    if (svx_proc_man::procs.num() != 0 ||
        svx_proc_man::cancel_events.num() != 0 ||
        svx_proc_man::cancel_requested_by_index.num() != 0)
      $fatal(1, "shutdown retained process-manager entries");
    $display("SVX_PROCESS_LIFETIME_SHUTDOWN_PASS");
    $finish;
  end
endmodule
