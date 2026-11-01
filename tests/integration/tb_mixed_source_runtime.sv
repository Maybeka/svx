`include "sv/svx_pkg.sv"
`ifdef SVX_PUBLIC_SOURCE_CLI
`include ".tmp/mixed_source_unit/integrated/source.sv"
`else
`include "tests/integration/external_bus_if.sv"
`include ".tmp/mixed_source_unit/common.svh"
`include ".tmp/mixed_source_unit/source.sv"
`endif

module tb;
  import svx_pkg::*;
  typedef svx_external_handles_pkg::SVXExternal_sv_hvif_c_s_sexternal_ubus_uif_smaster VifAdapter;
  mixed_source_pkg::A a;
  mixed_source_pkg::C python_c;
  mixed_source_pkg::Holder holder;
`ifdef SVX_MULTI_ENDPOINT_TYPES
  endpoint_types_pkg::Packet packet;
`else
  mixed_source_pkg::Packet packet;
`endif
  external_bus_if bus();
  svx_mirror_sv_mixed_source_pkg_C::C sv_c;
  svx_proxy_mixed_python_source::Root root_handle;
  svx_mirror_sv_mixed_source_pkg_Grandchild::Grandchild sv_final;
  mixed_source_pkg::Child python_derived;
  mixed_source_pkg::Grandchild python_final;
  svx_proxy_mixed_python_source::IndependentFactory#(later_source_pkg::IndependentLaterImpl) independent_factory;
  initial begin
    svx_init();
    svx_load("mixed_sv_source");
    svx_load("mixed_runtime_test");
    independent_factory = new();
    svx_start("mixed_independent.verify");
    if (mixed_source_pkg::Pure::allocations != 1)
      $fatal(1, "independent SV mirror did not construct exactly one source instance");
    if (mixed_source_pkg::A::allocations != 0)
      $fatal(1, "mixed-root registration allocated source receiver");
    svx_start("python_unit.types");
    sv_c = new();
    a = sv_c;
    if (a.check() != 135) $fatal(1, "mixed SV-root SV-origin dispatch failed");
    svx_start("same_package.verify_sv");
    svx_start("same_package.direct");
    svx_start("same_package.create");
    `SVX_GET_OBJECT(mixed_source_pkg::C, "same_package.c", python_c)
    a = python_c;
    if (a.check() != 142 || python_c.observed != 23)
      $fatal(1, "mixed SV-root Python-origin dispatch failed");
    python_c.peer = python_c;
    if (python_c.identity(python_c.peer) != python_c)
      $fatal(1, "mixed source proxy handle member/formal/return failed");
    holder = new();
    holder.peer = python_c;
    if (holder.identity(holder.peer) != python_c)
      $fatal(1, "mixed source forward proxy handle failed");
    holder.peer = null;
    packet = new();
    packet.value = 71;
    python_c.native_packet = packet;
    python_c.native_vif = bus;
    bus.data = 8'h31;
    svx_start("mixed_endpoint.verify");
    if (bus.data != 8'h5c) $fatal(1, "mixed endpoint did not update source VIF");
    python_c.peer = null;
    python_c.extra = 110;
    svx_start("same_package.close");
    sv_final = new(19);
    root_handle = sv_final;
    if (root_handle.check(1) != 1620)
      $fatal(1, "mixed Python-root SV-origin dispatch failed");
    sv_final.native_packet = packet;
    sv_final.native_vif = bus;
    svx_start("python_unit.verify_sv");
    if (bus.data != 8'h61) $fatal(1, "Python-root SV-origin endpoint write failed");
    svx_start("python_unit.create");
    `SVX_GET_OBJECT(mixed_source_pkg::Child, "python_unit.derived", python_derived)
    `SVX_GET_OBJECT(mixed_source_pkg::Grandchild, "python_unit.final", python_final)
    root_handle = python_derived;
    if (root_handle.check(1) != 1124) $fatal(1, "mixed Derived dispatch failed");
    root_handle = python_final;
    if (root_handle.check(1) != 1632) $fatal(1, "mixed Grandchild dispatch failed");
    if (python_final.proxy_scale(7) != 21)
      $fatal(1, "mixed source proxy static reference failed");
    python_derived.native_packet = packet;
    python_derived.native_vif = bus;
    python_final.native_packet = packet;
    python_final.native_vif = bus;
    svx_start("mixed_python_endpoint.verify");
    if (bus.data != 8'h63) $fatal(1, "Python-root Python-origin endpoint write failed");
    $display("MIXED_SOURCE_PROXY_REFERENCES_PASS");
    svx_start("python_unit.close");
    if (svx_external_handle_registry::objects.num() != 2 || VifAdapter::endpoints.size() != 1
        || svx_inheritance_registry::objects.num() != 1
        || !svx_inheritance_registry::objects.exists(VifAdapter::endpoints[0].object_id))
      $fatal(1, "mixed live endpoints or closed receivers mismatch");
    if (mixed_source_pkg::A::allocations != 3
        || svx_construction_context::frames.size() != 0)
      $fatal(1, "mixed receiver/context cleanup failed");
    svx_shutdown();
    if (svx_external_handle_registry::objects.num() != 0 || VifAdapter::endpoints.size() != 0
        || svx_inheritance_registry::objects.num() != 0)
      $fatal(1, "mixed shutdown did not clear external endpoints");
    $display("MIXED_SOURCE_RUNTIME_PASS");
    $finish;
  end
endmodule
