`include "sv/svx_pkg.sv"
`include ".tmp/python_root_namespaces/common.svh"
`include ".tmp/python_root_namespaces/svx_proxy_python_root_proxy_test.svh"

package python_root_probe_pkg;
  import svx_proxy_python_root_proxy_test::*;
  `include "tests/integration/python_root_child.svh"
endpackage

`include ".tmp/python_root_namespaces/svx_mirror_sv_python_root_probe_pkg_Child.svh"
`include ".tmp/python_root_namespaces/svx_proxy_python_root_derived.svh"

package python_root_e_probe_pkg;
  class Grandchild extends svx_proxy_python_root_derived::Derived;
    int e_value = 500;
    int observed_derived;
    function new(int e_seed, longint unsigned object_id = 0);
      super.new(e_seed, object_id);
      observed_derived = own_value;
    endfunction
    virtual function int check(int delta);
      return super.check(delta) + e_value;
    endfunction
    function int fixed(int delta);
      return count + delta + 700;
    endfunction
    function int observed_python();
      return observed_derived;
    endfunction
  endclass
endpackage

`include ".tmp/python_root_namespaces/svx_mirror_sv_python_root_e_probe_pkg_Grandchild.svh"

`ifndef PYTHON_ROOT_DECLARATIONS_ONLY
module tb;
  import svx_pkg::*;
  initial begin
    svx_proxy_python_root_proxy_test::Root root;
    svx_proxy_python_root_proxy_test::PlainRoot plain;
    svx_proxy_python_root_proxy_test::Root base_handle;
    python_root_probe_pkg::Child child;
    svx_mirror_sv_python_root_probe_pkg_Child::Child paired;
    svx_mirror_sv_python_root_e_probe_pkg_Grandchild::Grandchild sv_e;
    python_root_e_probe_pkg::Grandchild python_e;
    svx_dispatchable published;
    svx_init();
    if (svx_proxy_python_root_proxy_test::Root::scale(7) != 21)
      $fatal(1, "qualified root static dispatch failed");
    plain = new(13);
    if (plain.check(3) != 16) $fatal(1, "plain root callback failed");
    svx_release_object(plain.__svx_remote_object_id);
    root = new(41);
    if (root.count != 41 || root.check(1) != 42)
      $fatal(1, "qualified root field/callback failed");
    svx_release_object(root.__svx_remote_object_id);
    paired = new(81);
    base_handle = paired;
    if (base_handle.check(1) != 182 || paired.observed_root != 81 ||
        base_handle.fixed(1) != 282 || paired.fixed(1) != 382)
      $fatal(1, "qualified SV-origin C mirror failed");
    svx_release_object(paired.__svx_remote_object_id);
    svx_start("python_root.check_python_origin_child");
    svx_start("python_root.create_python_derived");
    `SVX_GET_OBJECT(python_root_probe_pkg::Child, "python_root.derived", child)
    base_handle = child;
    if (base_handle.check(1) != 1184 || child.base_check(1) != 84 ||
        base_handle.fixed(1) != 284 || child.fixed(1) != 384)
      $fatal(1, "qualified Python D virtual/super/nonvirtual dispatch failed");
    svx_release_object(child.__svx_remote_object_id);
    svx_start("python_root.check_python_derived_release");
    svx_load("tests.integration.python_root_namespace_test");
    begin
      svx_start("python_root_namespaces.create_e");
      `SVX_GET_OBJECT(python_root_e_probe_pkg::Grandchild, "python_root_namespaces.e", python_e)
      base_handle = python_e;
      if (base_handle.check(1) != 1692 || python_e.observed_derived != 1000)
        $fatal(1, "qualified Python-origin E dynamic dispatch failed");
      if (base_handle.__svx_remote_object_id != python_e.__svx_remote_object_id)
        $fatal(1, "qualified E created multiple receivers");
      python_e.count = 94;
      svx_start("python_root_namespaces.close_e");
    end
    if ($test$plusargs("ROOT_NAMESPACE_INIT_FAILURE")) begin
      sv_e = new(88);
      $fatal(1, "qualified failed constructor unexpectedly returned");
    end
    sv_e = new(93);
    base_handle = sv_e;
    if (base_handle.check(1) != 1694 || sv_e.observed_derived != 1000)
      $fatal(1, "qualified SV-origin E dynamic dispatch failed");
    svx_start("python_root_namespaces.verify_sv_e");
    svx_shutdown();
    $display("PYTHON_ROOT_PUBLIC_NAMESPACE_PASS");
    $finish;
  end
endmodule
`endif
