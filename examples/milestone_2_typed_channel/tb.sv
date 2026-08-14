`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/milestone_2_typed_channel/generated_types.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;
  import m2_typed_pkg::*;

  initial begin
    byte unsigned bytes[$];
    M2Transaction tx;

    $display("M2 typed channel test start @ %0.3f ns", $realtime);

    svx_init();
    svx_load("examples.milestone_2_typed_channel.tests.typed_test");

    svx_start("examples.milestone_2_typed_channel.tests.typed_test.python_puts_typed");

    svx_get_M2Transaction("m2.typed.py_to_sv", tx);
    if (tx.addr != 16'h1234) begin
      $fatal(2, "unexpected Python->SV addr: 0x%04h", tx.addr);
    end
    if (tx.data != -7) begin
      $fatal(2, "unexpected Python->SV data: %0d", tx.data);
    end
    $display("SV unpacked typed payload addr=0x%04h data=%0d", tx.addr, tx.data);

    fork
      begin
        svx_start("examples.milestone_2_typed_channel.tests.typed_test.python_gets_typed");
      end
      begin
        #(1.25ns);
        tx = new();
        tx.addr = 16'habcd;
        tx.data = 32'h10203040;
        svx_put_M2Transaction("m2.typed.sv_to_py", tx);
      end
    join

    fork
      begin
        svx_start("examples.milestone_2_typed_channel.tests.typed_test.python_rejects_type_mismatch");
      end
      begin
        #(1.25ns);
        tx = new();
        tx.addr = 16'h1111;
        tx.data = 1;
        bytes.delete();
        tx.pack(bytes);
        svx_channel_put_byte_queue(
          "m2.typed.bad_type",
          bytes,
          "svtypes",
          "WrongTransaction",
          "application/x-svtypes",
          "tests.M2Transaction",
          "fef7c9263d80226586c4e031a5ec2e5edaa8b4e5cc2eb39202fd4feb785cb4b5",
          1
        );
      end
    join

    $display("M2 typed channel test done @ %0.3f ns", $realtime);
    $finish;
  end
endmodule
