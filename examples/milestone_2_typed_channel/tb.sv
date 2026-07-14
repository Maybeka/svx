`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"

class M2Transaction extends svtypes_pkg::sv_object;
  bit [15:0] addr;
  int data;

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svx_obj_id();
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::pack_object_header("M2Transaction", 2, __svx_obj_id, bytes);
    svtypes_pkg::bits_packer#(bit [15:0])::pack(addr, bytes);
    svtypes_pkg::int_packer::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M2Transaction object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M2Transaction object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M2Transaction", 2, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::bits_packer#(bit [15:0])::unpack(addr, bytes, offset);
    svtypes_pkg::int_packer::unpack(data, bytes, offset);
  endfunction
endclass

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  initial begin
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    M2Transaction tx;

    $display("M2 typed channel test start @ %0.3f ns", $realtime);

    svx_init();
    svx_load("examples.milestone_2_typed_channel.tests.typed_test");

    svx_start("examples.milestone_2_typed_channel.tests.typed_test.python_puts_typed");

    svx_channel_get_payload("m2.typed.py_to_sv", payload);
    if (svx_payload_kind(payload) != "svtypes") begin
      $fatal(2, "unexpected typed kind: %s", svx_payload_kind(payload));
    end
    if (svx_payload_type_name(payload) != "M2Transaction") begin
      $fatal(2, "unexpected typed type: %s", svx_payload_type_name(payload));
    end
    if (svx_payload_content_type(payload) != "application/x-svtypes") begin
      $fatal(2, "unexpected typed content_type: %s", svx_payload_content_type(payload));
    end

    svx_payload_to_byte_queue(payload, bytes);
    svx_payload_destroy(payload);

    tx = new();
    offset = 0;
    tx.unpack(bytes, offset);
    if (offset != bytes.size()) begin
      $fatal(2, "SV unpack did not consume full payload: offset=%0d size=%0d", offset, bytes.size());
    end
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
        bytes.delete();
        tx.pack(bytes);
        svx_channel_put_byte_queue(
          "m2.typed.sv_to_py",
          bytes,
          "svtypes",
          "M2Transaction",
          "application/x-svtypes"
        );
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
          "application/x-svtypes"
        );
      end
    join

    $display("M2 typed channel test done @ %0.3f ns", $realtime);
    $finish;
  end
endmodule
