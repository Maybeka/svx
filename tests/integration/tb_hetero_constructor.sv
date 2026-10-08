`include "sv/svx_pkg.sv"
`include ".tmp/hetero_constructor/common.svh"
`include ".tmp/hetero_constructor/source.sv"
module tb;
  import svx_pkg::*;
  svx_proxy_hetero_constructor_source::Root base_handle;
  svx_mirror_sv_hetero_final_pkg_Grandchild::Grandchild sv_final;
  hetero_child_pkg::Child python_derived;
  hetero_final_pkg::Grandchild python_final;
  initial begin
    svx_init();
    svx_load("tests.integration.hetero_constructor_test");
    svx_start("hetero_constructor.defaults");
    if ($test$plusargs("HETERO_ROOT_FAILURE") || $test$plusargs("HETERO_DERIVED_FAILURE")) begin
      if ($test$plusargs("HETERO_ROOT_FAILURE")) svx_start("hetero_constructor.fail_root");
      else svx_start("hetero_constructor.fail");
      if ($test$plusargs("HETERO_PYTHON_FAILURE")) svx_start("hetero_constructor.fail_create");
      else sv_final = new();
      $fatal(1, "failing constructor unexpectedly returned");
    end
    if ($test$plusargs("HETERO_SUPER_TRANSFORM")) svx_start("hetero_constructor.transformed");
    sv_final = new(); base_handle = sv_final;
    if (base_handle.check(1) != 1621 || sv_final.actual_label != "abc")
      $fatal(1, "heterogeneous SV construction failed");
    svx_start("hetero_constructor.verify_sv");
    svx_start("hetero_constructor.create");
    `SVX_GET_OBJECT(hetero_child_pkg::Child, "hetero.derived", python_derived)
    `SVX_GET_OBJECT(hetero_final_pkg::Grandchild, "hetero.final", python_final)
    base_handle = python_derived;
    if (base_handle.check(1) != 1139 || python_derived.actual_label != "hello")
      $fatal(1, "heterogeneous Python Derived construction failed");
    base_handle = python_final;
    if (base_handle.check(1) != 1621 || python_final.actual_label != "abc")
      $fatal(1, "heterogeneous Python final construction failed");
    svx_start("hetero_constructor.close");
    if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0)
      $fatal(1, "heterogeneous constructor registry/context leaked");
    svx_shutdown();
    $display("HETERO_CONSTRUCTOR_PASS");
    $finish;
  end
  final begin
    if ($test$plusargs("HETERO_ROOT_FAILURE") || $test$plusargs("HETERO_DERIVED_FAILURE")) begin
      if (svx_inheritance_registry::objects.num() != 0 || svx_construction_context::frames.size() != 0 ||
          hetero_final_pkg::_svx_proxy_Derived_constructor_arguments::prepared.num() != 0 ||
          hetero_final_pkg::_svx_proxy_Derived_constructor_arguments::captured.num() != 0)
        $fatal(1, "failed constructor retained state");
      $display("HETERO_CONSTRUCTOR_ROLLBACK_SV_PASS");
    end
  end
endmodule
