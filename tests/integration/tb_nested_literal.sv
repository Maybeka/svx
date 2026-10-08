`include "sv/svx_pkg.sv"
`include ".tmp/nested_literal/common.svh"
`include ".tmp/nested_literal/source.sv"
class nested_factory implements same_package_pkg::nested_literal_factory;
  virtual function void spawn();
    svx_mirror_sv_same_package_pkg_A::A nested = new();
    if (nested.check() != 11) $fatal(1, "nested literal state mismatch");
    svx_pkg::svx_release_object_function(nested.__svx_remote_object_id);
    if (svx_pkg::svx_construction_context::frames.size() != 1)
      $fatal(1, "nested literal consumed outer frame");
    $display("NESTED_LITERAL_FRAME_RESTORED_PASS");
  endfunction
endclass
module tb;
  import svx_pkg::*;
  nested_factory factory;
  svx_mirror_sv_same_package_pkg_A::A a;
  svx_mirror_sv_same_package_pkg_C::C c;
  initial begin
    svx_init();
    svx_load("tests.integration.nested_literal_test");
    factory = new();
    same_package_pkg::A::nested_factory = factory;
    same_package_pkg::A::spawn_nested = 1;
    svx_start("nested_literal.create_a");
    same_package_pkg::A::spawn_nested = 1;
    svx_start("nested_literal.create_b");
    same_package_pkg::A::spawn_nested = 1;
    a = new();
    svx_start("nested_literal.verify_sv_a");
    same_package_pkg::A::spawn_nested = 1;
    c = new();
    svx_start("nested_literal.verify_sv_c");
    svx_start("nested_literal.verify_all_closed");
    if (same_package_pkg::A::allocations != 8 || svx_inheritance_registry::objects.num() != 0
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "nested literal final cleanup mismatch");
    svx_shutdown();
    $display("NESTED_LITERAL_PASS");
    $finish;
  end
endmodule
