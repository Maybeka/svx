// Generated from examples.milestone_7_sv_typed_helpers.tests.types
// Do not edit by hand.

typedef enum bit [7:0] {
  M7_OP_READ = 0,
  M7_OP_WRITE = 1
} M7BusOp;

typedef class M7BusReq;
typedef class M7BusRsp;
typedef class M7BusObs;

class M7BusReq extends svtypes_pkg::sv_object;
  rand int id;
  rand M7BusOp op;
  rand bit [7:0] addr;
  rand bit [31:0] data;

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1);
    return descriptor;
  endfunction

  static function svtypes_pkg::runtime_capabilities svtypes_runtime_capabilities();
    return svtypes_pkg::get_runtime_capabilities();
  endfunction

  virtual function void apply_plusargs(string prefix = "");
    string __svtypes_key;
    bit __svtypes_repeated;
    string __svtypes_enum_text_0;
    longint signed __svtypes_enum_value_0;
    __svtypes_repeated = svtypes_pkg::begin_plusarg_object(__svtypes_object_number);
    if (__svtypes_repeated) begin
      svtypes_pkg::end_plusarg_object();
      return;
    end
    __svtypes_key = (prefix == "") ? "id=%d" : {prefix, ".id=%d"};
    if ($test$plusargs((prefix == "") ? "id" : {prefix, ".id"}) && !$value$plusargs(__svtypes_key, id)) $fatal(2, "Malformed plusarg id");
    __svtypes_key = (prefix == "") ? "op=%s" : {prefix, ".op=%s"};
    if ($value$plusargs(__svtypes_key, __svtypes_enum_text_0)) begin
      case (__svtypes_enum_text_0)
        "M7_OP_READ": op = M7_OP_READ;
        "M7_OP_WRITE": op = M7_OP_WRITE;
        default: begin
          if ($sscanf(__svtypes_enum_text_0, "%d", __svtypes_enum_value_0) != 1) $fatal(2, "Malformed enum plusarg op=%s", __svtypes_enum_text_0);
          case (__svtypes_enum_value_0)
            0: op = M7BusOp'(__svtypes_enum_value_0);
            1: op = M7BusOp'(__svtypes_enum_value_0);
            default: $fatal(2, "Invalid enum plusarg op=%s", __svtypes_enum_text_0);
          endcase
        end
      endcase
    end
    __svtypes_key = (prefix == "") ? "addr=%h" : {prefix, ".addr=%h"};
    if ($test$plusargs((prefix == "") ? "addr" : {prefix, ".addr"}) && !$value$plusargs(__svtypes_key, addr)) $fatal(2, "Malformed plusarg addr");
    __svtypes_key = (prefix == "") ? "data=%h" : {prefix, ".data=%h"};
    if ($test$plusargs((prefix == "") ? "data" : {prefix, ".data"}) && !$value$plusargs(__svtypes_key, data)) $fatal(2, "Malformed plusarg data");
    svtypes_pkg::end_plusarg_object();
  endfunction

  virtual function string svtypes_sprint();
    string result;
    bit repeated;
    repeated = svtypes_pkg::begin_dump_object(__svtypes_object_number);
    if (repeated) begin
      result = $sformatf("<ref#%0d>", __svtypes_object_number);
      svtypes_pkg::end_dump_object();
      return result;
    end
    result = $sformatf("M7BusReq#%0d{", __svtypes_object_number);
    result = {result, "id="};
    result = {result, $sformatf("%0d", id)};
    result = {result, ", op="};
    result = {result, $sformatf("M7BusOp.%s", op.name())};
    result = {result, ", addr="};
    result = {result, $sformatf("%0h", addr)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", data)};
    result = {result, "}"};
    svtypes_pkg::end_dump_object();
    return result;
  endfunction

  virtual function void svtypes_display();
    $display("%s", svtypes_sprint());
  endfunction

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
    svtypes_pkg::end_pack_graph();
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svtypes_object_number();
    svtypes_pkg::register_object(this);
    svtypes_pkg::pack_object_header("milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 4, __svtypes_object_number, bytes);
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
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 4, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(M7BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bits_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M7BusReq__svtypes_coverage;
  covergroup cg with function sample(M7BusReq item);
    option.per_instance = 1;
    id_cp: coverpoint item.id;
    op_cp: coverpoint item.op;
    addr_cp: coverpoint item.addr;
    data_cp: coverpoint item.data;
  endgroup

  function new();
    cg = new();
  endfunction

  function void sample(M7BusReq item);
    cg.sample(item);
  endfunction
endclass

class M7BusRsp extends svtypes_pkg::sv_object;
  rand int id;
  rand bit [0:0] ok;
  rand bit [31:0] data;

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 1);
    return descriptor;
  endfunction

  static function svtypes_pkg::runtime_capabilities svtypes_runtime_capabilities();
    return svtypes_pkg::get_runtime_capabilities();
  endfunction

  virtual function void apply_plusargs(string prefix = "");
    string __svtypes_key;
    bit __svtypes_repeated;
    __svtypes_repeated = svtypes_pkg::begin_plusarg_object(__svtypes_object_number);
    if (__svtypes_repeated) begin
      svtypes_pkg::end_plusarg_object();
      return;
    end
    __svtypes_key = (prefix == "") ? "id=%d" : {prefix, ".id=%d"};
    if ($test$plusargs((prefix == "") ? "id" : {prefix, ".id"}) && !$value$plusargs(__svtypes_key, id)) $fatal(2, "Malformed plusarg id");
    __svtypes_key = (prefix == "") ? "ok=%h" : {prefix, ".ok=%h"};
    if ($test$plusargs((prefix == "") ? "ok" : {prefix, ".ok"}) && !$value$plusargs(__svtypes_key, ok)) $fatal(2, "Malformed plusarg ok");
    __svtypes_key = (prefix == "") ? "data=%h" : {prefix, ".data=%h"};
    if ($test$plusargs((prefix == "") ? "data" : {prefix, ".data"}) && !$value$plusargs(__svtypes_key, data)) $fatal(2, "Malformed plusarg data");
    svtypes_pkg::end_plusarg_object();
  endfunction

  virtual function string svtypes_sprint();
    string result;
    bit repeated;
    repeated = svtypes_pkg::begin_dump_object(__svtypes_object_number);
    if (repeated) begin
      result = $sformatf("<ref#%0d>", __svtypes_object_number);
      svtypes_pkg::end_dump_object();
      return result;
    end
    result = $sformatf("M7BusRsp#%0d{", __svtypes_object_number);
    result = {result, "id="};
    result = {result, $sformatf("%0d", id)};
    result = {result, ", ok="};
    result = {result, $sformatf("%0h", ok)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", data)};
    result = {result, "}"};
    svtypes_pkg::end_dump_object();
    return result;
  endfunction

  virtual function void svtypes_display();
    $display("%s", svtypes_sprint());
  endfunction

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
    svtypes_pkg::end_pack_graph();
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svtypes_object_number();
    svtypes_pkg::register_object(this);
    svtypes_pkg::pack_object_header("milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 3, __svtypes_object_number, bytes);
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
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 3, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(bit [0:0])::unpack(ok, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M7BusRsp__svtypes_coverage;
  covergroup cg with function sample(M7BusRsp item);
    option.per_instance = 1;
    id_cp: coverpoint item.id;
    ok_cp: coverpoint item.ok;
    data_cp: coverpoint item.data;
  endgroup

  function new();
    cg = new();
  endfunction

  function void sample(M7BusRsp item);
    cg.sample(item);
  endfunction
endclass

class M7BusObs extends svtypes_pkg::sv_object;
  rand int id;
  rand M7BusOp op;
  rand bit [7:0] addr;
  rand bit [31:0] data;

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1);
    return descriptor;
  endfunction

  static function svtypes_pkg::runtime_capabilities svtypes_runtime_capabilities();
    return svtypes_pkg::get_runtime_capabilities();
  endfunction

  virtual function void apply_plusargs(string prefix = "");
    string __svtypes_key;
    bit __svtypes_repeated;
    string __svtypes_enum_text_0;
    longint signed __svtypes_enum_value_0;
    __svtypes_repeated = svtypes_pkg::begin_plusarg_object(__svtypes_object_number);
    if (__svtypes_repeated) begin
      svtypes_pkg::end_plusarg_object();
      return;
    end
    __svtypes_key = (prefix == "") ? "id=%d" : {prefix, ".id=%d"};
    if ($test$plusargs((prefix == "") ? "id" : {prefix, ".id"}) && !$value$plusargs(__svtypes_key, id)) $fatal(2, "Malformed plusarg id");
    __svtypes_key = (prefix == "") ? "op=%s" : {prefix, ".op=%s"};
    if ($value$plusargs(__svtypes_key, __svtypes_enum_text_0)) begin
      case (__svtypes_enum_text_0)
        "M7_OP_READ": op = M7_OP_READ;
        "M7_OP_WRITE": op = M7_OP_WRITE;
        default: begin
          if ($sscanf(__svtypes_enum_text_0, "%d", __svtypes_enum_value_0) != 1) $fatal(2, "Malformed enum plusarg op=%s", __svtypes_enum_text_0);
          case (__svtypes_enum_value_0)
            0: op = M7BusOp'(__svtypes_enum_value_0);
            1: op = M7BusOp'(__svtypes_enum_value_0);
            default: $fatal(2, "Invalid enum plusarg op=%s", __svtypes_enum_text_0);
          endcase
        end
      endcase
    end
    __svtypes_key = (prefix == "") ? "addr=%h" : {prefix, ".addr=%h"};
    if ($test$plusargs((prefix == "") ? "addr" : {prefix, ".addr"}) && !$value$plusargs(__svtypes_key, addr)) $fatal(2, "Malformed plusarg addr");
    __svtypes_key = (prefix == "") ? "data=%h" : {prefix, ".data=%h"};
    if ($test$plusargs((prefix == "") ? "data" : {prefix, ".data"}) && !$value$plusargs(__svtypes_key, data)) $fatal(2, "Malformed plusarg data");
    svtypes_pkg::end_plusarg_object();
  endfunction

  virtual function string svtypes_sprint();
    string result;
    bit repeated;
    repeated = svtypes_pkg::begin_dump_object(__svtypes_object_number);
    if (repeated) begin
      result = $sformatf("<ref#%0d>", __svtypes_object_number);
      svtypes_pkg::end_dump_object();
      return result;
    end
    result = $sformatf("M7BusObs#%0d{", __svtypes_object_number);
    result = {result, "id="};
    result = {result, $sformatf("%0d", id)};
    result = {result, ", op="};
    result = {result, $sformatf("M7BusOp.%s", op.name())};
    result = {result, ", addr="};
    result = {result, $sformatf("%0h", addr)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", data)};
    result = {result, "}"};
    svtypes_pkg::end_dump_object();
    return result;
  endfunction

  virtual function void svtypes_display();
    $display("%s", svtypes_sprint());
  endfunction

  virtual function void pack(ref byte unsigned bytes[$]);
    svtypes_pkg::begin_pack_graph();
    svtypes_pkg::pack_object_value(this, bytes);
    svtypes_pkg::end_pack_graph();
  endfunction

  virtual function void pack_body(ref byte unsigned bytes[$]);
    ensure_svtypes_object_number();
    svtypes_pkg::register_object(this);
    svtypes_pkg::pack_object_header("milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 4, __svtypes_object_number, bytes);
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
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 4, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bits_packer#(M7BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bits_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bits_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction
endclass

class M7BusObs__svtypes_coverage;
  covergroup cg with function sample(M7BusObs item);
    option.per_instance = 1;
    id_cp: coverpoint item.id;
    op_cp: coverpoint item.op;
    addr_cp: coverpoint item.addr;
    data_cp: coverpoint item.data;
  endgroup

  function new();
    cg = new();
  endfunction

  function void sample(M7BusObs item);
    cg.sample(item);
  endfunction
endclass

// SvTypes typed channel helpers
task automatic svx_get_M7BusReq(string channel_name, output M7BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusReq", "milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1, "svx_get_M7BusReq", bytes);
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
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusReq", "milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1, "svx_peek_M7BusReq", bytes);
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
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M7BusReq", "application/x-svtypes", "milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1);
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
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusReq", "milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1, "svx_try_get_M7BusReq", bytes);
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
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M7BusReq", "application/x-svtypes", "milestone_7_sv_typed_helpers.M7BusReq", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1);
endfunction

task automatic svx_get_M7BusRsp(string channel_name, output M7BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusRsp", "milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 1, "svx_get_M7BusRsp", bytes);
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
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusRsp", "milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 1, "svx_peek_M7BusRsp", bytes);
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
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M7BusRsp", "application/x-svtypes", "milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 1);
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
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusRsp", "milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 1, "svx_try_get_M7BusRsp", bytes);
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
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M7BusRsp", "application/x-svtypes", "milestone_7_sv_typed_helpers.M7BusRsp", "81140f649abab1c51732ba066c212f81e351046ba08a520b2d7b8859f9de319e", 1);
endfunction

task automatic svx_get_M7BusObs(string channel_name, output M7BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusObs", "milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1, "svx_get_M7BusObs", bytes);
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
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusObs", "milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1, "svx_peek_M7BusObs", bytes);
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
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M7BusObs", "application/x-svtypes", "milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1);
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
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M7BusObs", "milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1, "svx_try_get_M7BusObs", bytes);
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
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M7BusObs", "application/x-svtypes", "milestone_7_sv_typed_helpers.M7BusObs", "d79c2045dd73e17843e79ecf988181381227e096e5ea8ccf6d4bdd748411b5de", 1);
endfunction
