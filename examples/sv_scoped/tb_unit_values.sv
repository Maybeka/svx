// SPDX-License-Identifier: Apache-2.0
`include "examples/sv_scoped/unit_values.sv"

module tb_unit_values;
  initial begin
    Packet packet = INITIAL;
    PacketAlias alias_value = INITIAL;
    Holder::Payload payload = 10'h1a5;
    if (START != ACTIVE || DEPTH != 9 || $bits(Word) != 13)
      $fatal(1, "unit alias or constant mismatch");
    if (packet.mode != 5 || packet.flags !== 4'b10xz || alias_value !== packet)
      $fatal(1, "unit packed constant mismatch");
    if ($bits(payload) != 10 || payload.state != Holder::ON || payload.data != 8'ha5)
      $fatal(1, "nested unit value mismatch");
    $display("UNIT_VALUES_NATIVE_PASS");
    $finish;
  end
endmodule
