`include "sv/svx_pkg.sv"
`include "tests/integration/external_bus_if.sv"
`include ".tmp/mixed_source_unit/common.svh"
`include ".tmp/mixed_source_unit/source.sv"

module tb;
  svx_proxy_mixed_sv_source::B sv_root_proxy;
  svx_proxy_mixed_python_source::Root python_root_proxy;
  svx_proxy_mixed_python_source::Derived python_derived_proxy;
  mixed_source_pkg::C sv_root_child;
  mixed_source_pkg::Child python_root_child;
  mixed_source_pkg::Grandchild python_root_final;

  initial begin
    if (mixed_source_pkg::Pure::allocations != 0)
      $fatal(1, "independent mirror registration allocated source instance");
    if (mixed_source_pkg::A::allocations != 0)
      $fatal(1, "mixed-root helper registration allocated the user base");
    if (sv_root_proxy != null || python_root_proxy != null || python_derived_proxy != null ||
        sv_root_child != null || python_root_child != null || python_root_final != null)
      $fatal(1, "mixed-root layout unexpectedly allocated user objects");
    $display("MIXED_SOURCE_UNIT_TYPES_PASS");
    $finish;
  end
endmodule
