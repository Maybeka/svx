`include "sv/svx_pkg.sv"
`include "tests/integration/sv_field_owner.sv"
`include ".tmp/sv_initiated_boundary/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_mirror_sv_field_owner_pkg_Base::Base value;
    svx_init();
    svx_load("tests.integration.sv_initiated_boundary_test");
    svx_start("sv_initiated_boundary.create_python");
    if (svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "Python-origin mirror leaked its receiver");
    value = new();
    svx_start("sv_initiated_boundary.verify");
    if (value.get_flags() !== 4'b10zx)
      $fatal(1, "four-state mirrored field lost X/Z on SV-origin receiver");
    svx_release_object(value.__svx_remote_object_id);
    svx_start("sv_initiated_boundary.verify_closed");
    if (svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "SV-origin mirror leaked its receiver");
    svx_shutdown();
    $display("SV_INITIATED_BOUNDARY_PASS");
    $finish;
  end
endmodule
