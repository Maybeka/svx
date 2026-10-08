`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "tests/integration/unnamed_specialization_types.sv"
`include ".tmp/unnamed_specialization/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    unnamed_specialization_pkg::Root#(byte,5) byte_handle;
    unnamed_specialization_pkg::Root#(shortint unsigned,17) short_handle;
    svx_init();
    svx_load("tests.integration.unnamed_specialization_test");
    svx_start("unnamed_specialization.create");
    `SVX_GET_OBJECT(unnamed_specialization_pkg::Root#(byte,5), "unnamed.byte", byte_handle)
    `SVX_GET_OBJECT(unnamed_specialization_pkg::Root#(shortint unsigned,17), "unnamed.short", short_handle)
    if (byte_handle.item != -23 || short_handle.item != 65535)
      $fatal(1, "specialized inherited fields lost shared storage");
    if ($bits(byte_handle.flags) != 5 || $bits(short_handle.flags) != 17)
      $fatal(1, "specialized inherited field widths changed");
    if (byte_handle.echo(-9) != -8 || short_handle.echo(65000) != 65002)
      $fatal(1, "specialized virtual callback or super dispatch failed");
    $display("UNNAMED_SPECIALIZATION_CALLBACK_PASS");
    svx_start("unnamed_specialization.close");
    svx_shutdown();
    $finish;
  end
endmodule
