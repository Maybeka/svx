module type_identity_tb;
  import svx_pkg::*;
  initial begin
    type_identity_pkg::Driver#() native_handle;
    svx_mirror_sv_type_identity_pkg_Driver::Driver mirror;
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.type_identity_entry");
    mirror = new(17);
    native_handle = mirror;
    assert (native_handle.same(mirror)) else $fatal(1, "specialization identity changed");
    svx_start("type_identity.run");
    svx_shutdown();
    $display("TYPE_IDENTITY_NATIVE_PASS");
    $finish;
  end
endmodule
