`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/project_migration/generated/models.sv"
`include "examples/project_migration/common/dut.sv"

module tb;
  `include "examples/project_migration/common/harness.svh"
  import svx_pkg::*;
  `include "examples/project_migration/common/typed_boundary.svh"
  initial begin
    string python_module, python_test;
    if (!$value$plusargs("MIGRATION_MODULE=%s", python_module))
      python_module = "examples.project_migration.scenarios";
    if (!$value$plusargs("MIGRATION_TEST=%s", python_test)) python_test = "smoke";
    svx_init();
    fork
      driver();
      monitor();
      request_bridge();
      response_bridge();
      monitor_bridge();
      svx_run_test(python_module, python_test);
    join
    check_complete();
    svx_shutdown();
    report_complete();
  end
endmodule
