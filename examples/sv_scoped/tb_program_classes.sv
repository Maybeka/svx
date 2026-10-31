// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
`include "examples/sv_scoped/program_classes.sv"
module tb_program_classes;
  import svx_pkg::*;
  sv_example_program_owner#(8) a(),b();
  sv_example_program_owner#(13) c();
  svx_exports exports();
  initial begin
    svx_init();
    exports.initialize();
    if($time!=0)$fatal(1,"program startup advanced time");
    svx_load("examples.sv_scoped.program_classes");
    svx_start("program_classes.run");
    if($time!=1)$fatal(1,"program task timing");
    svx_shutdown();
    $display("PROGRAM_CLASSES_NATIVE_PASS");
    $finish;
  end
endmodule
