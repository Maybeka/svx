// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
`include "examples/sv_scoped/instance_classes.sv"
module tb_instance_classes;
  import svx_pkg::*;
  sv_example_instance_owner#(8) a(),b();
  sv_example_instance_owner#(13) c();
  svx_exports exports();
  initial begin
    a.owner_state=10;b.owner_state=20;c.owner_state=30;
    svx_init();
    exports.initialize();
    svx_load("examples.sv_scoped.instance_classes");
    svx_start("instance_classes.run");
    a.check_published("instance.a",13,10);
    b.check_published("instance.b",1037,20);
    c.check_published("instance.c",35,30);
    if($time!=2) $fatal(1,"instance task timing");
    svx_shutdown();
    $display("INSTANCE_CLASSES_NATIVE_PASS");
    $finish;
  end
endmodule
