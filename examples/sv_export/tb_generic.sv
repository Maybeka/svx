// SPDX-License-Identifier: Apache-2.0
`include "sv/svx_defs.svh"
module generic_class_constants_tb;
  import svx_pkg::*;
  initial begin
    generic_class_constants_pkg::Wide published;
    svx_init();
    svx_exports_pkg::initialize();
    if ($test$plusargs("SVX_GENERIC_ONLY_CALLABLES")) begin
      svx_load("examples.sv_export.generic_calls");
      svx_start("generic_class_calls.run");
    end else begin
      svx_load("examples.sv_export.generic_entry");
      svx_start("generic_class_values.run");
      `SVX_GET_OBJECT(generic_class_constants_pkg::Wide, "generic.wide", published)
      if (published.score(2) != 172 || published.get_value() != 70)
        $fatal(1, "closed-alias virtual callback/super did not preserve WIDTH=70");
    end
    if ($bits(generic_class_constants_pkg::Narrow::Mode) != 9 ||
        $bits(generic_class_constants_pkg::Wide::Mode) != 70)
      $fatal(1, "native class alias widths do not match the Python views");
    if ($time != ($test$plusargs("SVX_GENERIC_ONLY_CALLABLES") ? 1ns : 2ns))
      $fatal(1, "native packet tasks did not each consume 1ns");
    svx_shutdown();
    $display("GENERIC_CLASS_VALUES_NATIVE_PASS");
    $finish;
  end
endmodule
