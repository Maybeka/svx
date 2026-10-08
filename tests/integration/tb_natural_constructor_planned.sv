`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/natural_constructor_planned/integrated/source.sv"

module tb;
  import svx_pkg::*;
  svx_mirror_sv_natural_bridge_child_pkg_C::C instance;
  natural_bridge_pkg::Packet packet;
  initial begin
    svx_init();
    svx_load("tests.integration.natural_constructor_bridge");
    if ($test$plusargs("NATURAL_CONSTRUCTOR_FAIL_AFTER"))
      svx_start("natural_bridge.fail_planned");
    packet = new();
    instance = new(7, "alpha", packet);
    if (instance.count != 1120 || instance.local_value != 217 ||
        instance.label != "alpha-C-B" || instance.packet != packet)
      $fatal(1, "planned natural constructor arguments or fields failed");
    if (svx_construction_context::frames.size() != 0)
      $fatal(1, "planned natural constructor retained its context");
    svx_start("natural_bridge.verify_planned");
    $display("NATURAL_PLANNED_SV_PASS");
    svx_shutdown();
    $finish;
  end
  final begin
    if ($test$plusargs("NATURAL_CONSTRUCTOR_FAIL_AFTER")) begin
      if (svx_inheritance_registry::objects.num() != 0 ||
          svx_construction_context::frames.size() != 0 ||
          natural_bridge_proxy_pkg::_svx_proxy_B_constructor_arguments::prepared.num() != 0 ||
          natural_bridge_proxy_pkg::_svx_proxy_B_constructor_arguments::captured.num() != 0)
        $fatal(1, "failed natural constructor retained SV state");
      $display("NATURAL_ROLLBACK_SV_PASS");
    end
  end
endmodule
