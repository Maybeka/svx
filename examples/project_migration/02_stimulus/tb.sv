`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/project_migration/generated/models.sv"
`include "examples/project_migration/common/dut.sv"

module tb;
  `include "examples/project_migration/common/harness.svh"
  import svx_pkg::*;
  `include "examples/project_migration/common/typed_boundary.svh"
  initial begin
    svx_init();
    fork
      driver();
      monitor();
      request_bridge();
      response_bridge();
      legacy_scoreboard();
      svx_run_test("examples.project_migration.scenarios", "stimulus");
    join
    check_complete();
    svx_shutdown();
    report_complete();
  end
endmodule
