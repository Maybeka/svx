`include "sv/svx_pkg.sv"
`include "examples/project_migration/common/legacy_types.svh"
`include "examples/project_migration/common/dut.sv"

module tb;
  `include "examples/project_migration/common/harness.svh"
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_run_test("examples.project_migration.scenarios", "entry");
    fork
      driver();
      monitor();
      legacy_sequence();
      legacy_responses();
      legacy_scoreboard();
    join
    check_complete();
    svx_shutdown();
    report_complete();
  end
endmodule
