// SPDX-License-Identifier: Apache-2.0
module parameterized_vif_tb;
  import svx_pkg::*;
  parameter_bus normal();
  parameter_bus#(13,2) wide();
  parameter_bus#(13,2,bit[6:0]) typed();
  parameter_bus#(.Word(parameterized_vif_types_pkg::Mode)) enums();
  parameter_bus#(.Word(parameterized_vif_types_pkg::Payload)) structs();
  initial begin
    parameterized_vif_pkg::Owner::set_buses(normal,wide,typed);
    parameterized_vif_pkg::Owner::set_named_buses(enums,structs);
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.parameterized_vif_entry");
    svx_start("parameterized_vif.run");
    if (normal.data!=8'h9a || wide.data!=13'h1234 || typed.data!=7'h56)
      $fatal(1,"parameterized data write mismatch");
    if (normal.lanes[2]!=3 || wide.lanes[0]!=13'h1234 || wide.lanes[1]!=13'h1fff)
      $fatal(1,"parameterized array write mismatch");
    if ($time!=3ns) $fatal(1,"parameterized tasks did not advance time");
    if (enums.data!=parameterized_vif_types_pkg::ACTIVE || structs.data.data!=8'ha5)
      $fatal(1,"nominal type parameter write mismatch");
    svx_shutdown();
    $display("PARAMETERIZED_VIF_SV_PASS");
    $finish;
  end
endmodule
