`include "examples/project_migration/common/legacy_types.svh"
`include "examples/project_migration/common/dut.sv"

module tb;
  `include "examples/project_migration/common/harness.svh"
  initial begin
    fork
      driver();
      monitor();
      legacy_sequence();
      legacy_responses();
      legacy_scoreboard();
    join
    check_complete();
    report_complete();
  end
endmodule
