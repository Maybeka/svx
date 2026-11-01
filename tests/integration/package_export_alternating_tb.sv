`timescale 1ns/1ps
`include "sv/svx_defs.svh"
module package_export_chain_tb;
  import svx_pkg::*;
  export_chain_pkg::NativeBase native_handle;
  export_chain_pkg::A chain_handle;
  initial begin
    svx_init();
    // SVX_GENERATED_STARTUP
    svx_load("tests.integration.package_export_alternating");
    svx_start("package_chain.run");
    `SVX_GET_OBJECT(export_chain_pkg::NativeBase, "package_chain.native", native_handle)
    `SVX_GET_OBJECT(export_chain_pkg::A, "package_chain.chain", chain_handle)
    if (native_handle.check() != 143) $fatal(1, "ordinary family Python callback");
    if (chain_handle.check() != 142) $fatal(1, "alternating family callback");
    if (export_chain_pkg::native_allocations != 1 ||
        export_chain_pkg::chain_allocations != 2) $fatal(1, "duplicate native construction");
    svx_shutdown();
    $display("PACKAGE_CHAIN_NATIVE_PASS");
    $finish;
  end
endmodule
