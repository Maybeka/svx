// SPDX-License-Identifier: Apache-2.0
module vif_array_dimensions_tb;
  import svx_pkg::*;
  array_dimensions_bus bus0();
  initial begin
    if ($unpacked_dimensions(bus0.values) != 1 || $bits(bus0.values[0]) != 8)
      $fatal(1, "incorrect single-dimensional signal shape");
    if ($unpacked_dimensions(bus0.vectors) != 2 || $bits(bus0.vectors[0][0]) != 24)
      $fatal(1, "incorrect multidimensional signal shape");
    bus0.values = '{1, 2, 3, 4};
    bus0.vectors = '{'{24'h123456, 24'h234567, 24'h345678},
                     '{24'h456789, 24'h56789a, 24'h6789ab}};
    array_dimensions_pkg::Owner::set_bus(bus0);
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.vif_array_dimensions_entry");
    svx_start("array_dimensions.run");
    foreach (bus0.values[i])
      if (bus0.values[i] != (i+1)*11) $fatal(1, "array write mismatch");
    if (bus0.vectors[0][0] != 24'habcdef || bus0.vectors[0][1] != 24'h102030 ||
        bus0.vectors[0][2] != 24'h405060 || bus0.vectors[1][0] != 24'h708090 ||
        bus0.vectors[1][1] != 24'ha0b0c0 || bus0.vectors[1][2] != 24'hd0e0f0)
      $fatal(1, "multidimensional array write mismatch");
    svx_shutdown();
    $display("VIF_ARRAY_DIMENSIONS_SV_PASS");
    $finish;
  end
endmodule
