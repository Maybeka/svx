`define SV_ROOT_DECLARATIONS_ONLY
`include "tests/integration/tb_sv_root_target.sv"
`include ".tmp/sv_root_target/b2.svh"
package sv_root_branch_pkg;
  class C2 extends svx_proxy_sv_root_branch_test::B2;
    int extra = 200;
    int observed;
    function new();
      super.new();
      observed = retry;
    endfunction
    virtual function int check();
      return super.check() + extra;
    endfunction
    function int observed_value();
      return observed;
    endfunction
  endclass
endpackage
`include ".tmp/sv_root_target/c2.svh"

module tb;
  import svx_pkg::*;
  sv_root_pkg::A first, other;
  svx_mirror_sv_sv_root_pkg_A::A plain;
  svx_mirror_sv_sv_root_child_pkg_C::C c;
  svx_mirror_sv_sv_root_branch_pkg_C2::C2 c2;
  initial begin
    svx_init();
    plain = new();
    if (plain.count != 11 || plain.check() != 11)
      $fatal(1, "root mirror selected a Python branch implicitly");
    svx_release_object(plain.__svx_remote_object_id);
    $display("SV_ROOT_BRANCHES_PLAIN_A_PASS");
    svx_start("sv_root_branches.create");
    `SVX_GET_OBJECT(sv_root_pkg::A, "sv_root_branches.c1", first)
    `SVX_GET_OBJECT(sv_root_pkg::A, "sv_root_branches.c2", other)
    if (first.check() != 135 || other.check() != 262)
      $fatal(1, "Python-origin branch dispatch crossed receivers");
`ifdef SV_ROOT_PREFIX
    if (first.prefix_virtual() != 423 || other.prefix_virtual() != 400)
      $fatal(1, "Python-origin prefix virtual slot selected the wrong branch");
`endif
    svx_start("sv_root_branches.close");
    c = new();
    c2 = new();
    first = c;
    other = c2;
    if (first.check() != 135 || other.check() != 262)
      $fatal(1, "SV-origin branch selector initialized the wrong Python portion");
`ifdef SV_ROOT_PREFIX
    if (first.prefix_virtual() != 423 || other.prefix_virtual() != 400)
      $fatal(1, "SV-origin prefix virtual slot selected the wrong branch");
`endif
    svx_start("sv_root_branches.verify_sv");
    if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0)
      $fatal(1, "branch receiver or constructor context leaked");
`ifdef SV_ROOT_PREFIX
    if (sv_root_prefix_pkg::Z::allocations != 5)
      $fatal(1, "shared prefix added an unexpected source allocation");
    $display("SV_ROOT_BRANCHES_PREFIX_PASS");
`endif
    svx_shutdown();
    $display("SV_ROOT_BRANCHES_PASS");
    $finish;
  end
endmodule
