`include "tests/integration/sv_field_owner.sv"
`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/standalone_mirror/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.standalone_mirror_test");
    svx_start("standalone_mirror.run");
    if (svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "standalone mirror leaked an SV receiver");
    svx_shutdown();
    $finish;
  end
endmodule
