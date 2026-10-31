// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
`include "examples/sv_scoped/generate_classes.sv"
module tb_generate_classes;
  import svx_pkg::*;
  sv_example_generate_owner#(8) a(),b();
  sv_example_generate_owner#(13) c();
  svx_exports exports();
  initial begin
    a.owner_state=10;b.owner_state=20;c.owner_state=30;
    svx_init();
    exports.initialize();
    svx_load("examples.sv_scoped.generate_classes");
    svx_start("generate_classes.run");
    a.lane[0].active.check_published("generate.a0",11,10);
    a.lane[1].active.check_published("generate.a1",13,10);
    b.lane[0].active.check_published("generate.b0",28,20);
    b.lane[1].active.check_published("generate.b1",1038,20);
    c.lane[0].active.check_published("generate.c0",35,30);
    c.lane[1].active.check_published("generate.c1",37,30);
    if($time!=1)$fatal(1,"generate task timing");
    svx_shutdown();
    $display("GENERATE_CLASSES_NATIVE_PASS");
    $finish;
  end
endmodule
