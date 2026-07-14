// Generated from examples.milestone_7_sv_typed_helpers.tests.types
// Do not edit by hand.

typedef enum int {
  M7_OP_READ = 0,
  M7_OP_WRITE = 1
} M7BusOp;

typedef class M7BusReq;
typedef class M7BusRsp;
typedef class M7BusObs;

class M7BusReq extends svtypes_pkg::sv_object;
  int id;
  M7BusOp op;
  bit [7:0] addr;
  bit [31:0] data;

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svx_obj_id();
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::pack_object_header("M7BusReq", 4, __svx_obj_id, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bits_packer#(M7BusOp)::pack(op, bytes);
    svtypes_pkg::bits_packer#(bit [7:0])::pack(addr, bytes);
    svtypes_pkg::bits_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M7BusReq object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M7BusReq object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M7BusReq", 4, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(M7BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bits_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M7BusRsp extends svtypes_pkg::sv_object;
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
    svtypes_pkg::pack_object_header("M7BusRsp", 3, __svx_obj_id, bytes);
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
      $fatal(2, "SvTypes cannot unpack root reference into existing M7BusRsp object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M7BusRsp object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M7BusRsp", 3, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(bit [0:0])::unpack(ok, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M7BusObs extends svtypes_pkg::sv_object;
  int id;
  M7BusOp op;
  bit [7:0] addr;
  bit [31:0] data;

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svx_obj_id();
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::pack_object_header("M7BusObs", 4, __svx_obj_id, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bits_packer#(M7BusOp)::pack(op, bytes);
    svtypes_pkg::bits_packer#(bit [7:0])::pack(addr, bytes);
    svtypes_pkg::bits_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M7BusObs object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M7BusObs object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svx_obj_id;
    svtypes_pkg::unpack_object_header("M7BusObs", 4, incoming_svx_obj_id, bytes, offset);
    __svx_obj_id = incoming_svx_obj_id;
    svtypes_pkg::register_svx_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(M7BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bits_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

// SvTypes typed channel helpers
task automatic svx_get_M7BusReq(string channel_name, output M7BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusReq", "svx_get_M7BusReq", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_M7BusReq", channel_name, "M7BusReq", offset, bytes.size());
endtask

task automatic svx_peek_M7BusReq(string channel_name, output M7BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusReq", "svx_peek_M7BusReq", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_M7BusReq", channel_name, "M7BusReq", offset, bytes.size());
endtask

task automatic svx_put_M7BusReq(string channel_name, input M7BusReq item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_M7BusReq(%s): cannot put null SvTypes object type M7BusReq", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M7BusReq", "application/x-svtypes");
endtask

task automatic svx_try_get_M7BusReq(string channel_name, output bit ok, output M7BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusReq", "svx_try_get_M7BusReq", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_M7BusReq", channel_name, "M7BusReq", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_M7BusReq(string channel_name, input M7BusReq item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_M7BusReq(%s): cannot put null SvTypes object type M7BusReq", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M7BusReq", "application/x-svtypes");
endfunction

task automatic svx_get_M7BusRsp(string channel_name, output M7BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusRsp", "svx_get_M7BusRsp", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_M7BusRsp", channel_name, "M7BusRsp", offset, bytes.size());
endtask

task automatic svx_peek_M7BusRsp(string channel_name, output M7BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusRsp", "svx_peek_M7BusRsp", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_M7BusRsp", channel_name, "M7BusRsp", offset, bytes.size());
endtask

task automatic svx_put_M7BusRsp(string channel_name, input M7BusRsp item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_M7BusRsp(%s): cannot put null SvTypes object type M7BusRsp", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M7BusRsp", "application/x-svtypes");
endtask

task automatic svx_try_get_M7BusRsp(string channel_name, output bit ok, output M7BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusRsp", "svx_try_get_M7BusRsp", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_M7BusRsp", channel_name, "M7BusRsp", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_M7BusRsp(string channel_name, input M7BusRsp item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_M7BusRsp(%s): cannot put null SvTypes object type M7BusRsp", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M7BusRsp", "application/x-svtypes");
endfunction

task automatic svx_get_M7BusObs(string channel_name, output M7BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusObs", "svx_get_M7BusObs", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_M7BusObs", channel_name, "M7BusObs", offset, bytes.size());
endtask

task automatic svx_peek_M7BusObs(string channel_name, output M7BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusObs", "svx_peek_M7BusObs", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_M7BusObs", channel_name, "M7BusObs", offset, bytes.size());
endtask

task automatic svx_put_M7BusObs(string channel_name, input M7BusObs item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_M7BusObs(%s): cannot put null SvTypes object type M7BusObs", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M7BusObs", "application/x-svtypes");
endtask

task automatic svx_try_get_M7BusObs(string channel_name, output bit ok, output M7BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusObs", "svx_try_get_M7BusObs", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_M7BusObs", channel_name, "M7BusObs", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_M7BusObs(string channel_name, input M7BusObs item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_M7BusObs(%s): cannot put null SvTypes object type M7BusObs", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M7BusObs", "application/x-svtypes");
endfunction
