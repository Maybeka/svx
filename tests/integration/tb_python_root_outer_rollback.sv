`define PYTHON_ROOT_DECLARATIONS_ONLY
`include "tests/integration/tb_python_root_namespaces.sv"

module tb;
  import svx_pkg::*;
  svx_proxy_python_root_proxy_test::Root existing;
  initial begin
    svx_init();
    svx_load("tests.integration.python_root_outer_rollback_test");
    svx_start("python_root_outer.run");
    `SVX_GET_OBJECT(svx_proxy_python_root_proxy_test::Root, "python_root_outer.existing", existing)
    if (existing.check(1) != 1184)
      $fatal(1, "reinitialization failure retired or changed the existing receiver");
    svx_start("python_root_outer.close_existing");
    if (svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "failed Python-root outer initializer retained SV objects");
    if (svx_inheritance_registry::published_object_ids.exists("python_root_outer.failed"))
      $fatal(1, "failed Python-root outer initializer retained publication");
    if (svx_inheritance_registry::published_object_ids.exists("python_root_outer.existing"))
      $fatal(1, "existing receiver publication survived explicit close");
    svx_shutdown();
    $display("PYTHON_ROOT_OUTER_ROLLBACK_PASS");
    $finish;
  end
endmodule
