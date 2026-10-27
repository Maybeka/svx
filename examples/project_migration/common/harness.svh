// Shared module body: hardware, clock/reset, BFMs, and completion checks.
timeunit 1ns;
timeprecision 1ps;
bit clk = 0;
bit reset_n = 0;
bit valid = 0;
bit write = 0;
bit [7:0] address = 0;
bit [31:0] wdata = 0;
wire [31:0] rdata;
wire ready;
bit corrupt_read = $test$plusargs("MIGRATION_CORRUPT_READ");
bit unknown_read = $test$plusargs("MIGRATION_UNKNOWN_READ");
migration_register_bank dut(clk, reset_n, valid, write, address, wdata,
                            corrupt_read, unknown_read, ready, rdata);
always #5ns clk = ~clk;
initial begin
  repeat (2) @(negedge clk);
  reset_n = 1;
end
`include "examples/project_migration/common/environment.svh"

task automatic check_complete();
  if (!driver_done || driven == 0 || driven != sampled || wait_cycles == 0)
    $fatal(2, "MIGRATION_INCOMPLETE driven=%0d sampled=%0d waits=%0d",
           driven, sampled, wait_cycles);
endtask

task automatic report_complete();
  $display("MIGRATION_PROJECT_PASS count=%0d observations=%0d waits=%0d", driven, sampled, wait_cycles);
  $finish;
endtask

initial begin
  #1ms;
  $fatal(2, "MIGRATION_TIMEOUT");
end
