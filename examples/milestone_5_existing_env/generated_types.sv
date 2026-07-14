// Generated from examples.milestone_5_existing_env.tests.types
// Do not edit by hand.

typedef enum int {
  M5_OP_READ = 0,
  M5_OP_WRITE = 1
} M5BusOp;

typedef class M5BusReq;
typedef class M5BusRsp;
typedef class M5BusObs;

class M5BusReq extends svtypes_pkg::sv_object;
  int id;
  M5BusOp op;
  bit [7:0] addr;
  bit [31:0] data;

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svx_obj_id();
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::pack_object_header("M5BusReq", 4, __svx_obj_id, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bits_packer#(M5BusOp)::pack(op, bytes);
    svtypes_pkg::bits_packer#(bit [7:0])::pack(addr, bytes);
    svtypes_pkg::bits_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M5BusReq object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M5BusReq object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M5BusReq", 4, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(M5BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bits_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M5BusRsp extends svtypes_pkg::sv_object;
  int id;
  bit [0:0] ok;
  bit [31:0] data;

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svx_obj_id();
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::pack_object_header("M5BusRsp", 3, __svx_obj_id, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bits_packer#(bit [0:0])::pack(ok, bytes);
    svtypes_pkg::bits_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M5BusRsp object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M5BusRsp object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M5BusRsp", 3, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(bit [0:0])::unpack(ok, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M5BusObs extends svtypes_pkg::sv_object;
  int id;
  M5BusOp op;
  bit [7:0] addr;
  bit [31:0] data;

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svx_obj_id();
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::pack_object_header("M5BusObs", 4, __svx_obj_id, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bits_packer#(M5BusOp)::pack(op, bytes);
    svtypes_pkg::bits_packer#(bit [7:0])::pack(addr, bytes);
    svtypes_pkg::bits_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M5BusObs object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M5BusObs object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M5BusObs", 4, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(M5BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bits_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass
