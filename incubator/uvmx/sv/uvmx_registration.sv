// Generated from uvmx.registration
// Do not edit by hand.

typedef class UvmxRegistration;

class UvmxRegistration extends svtypes_pkg::sv_object;
  string canonical_id;
  string factory_name;
  string sv_base;
  rand bit [0:0] finished;

  protected bit __svtypes_layered_randomize_active;
  protected int __svtypes_layered_randomize_priority;
  function bit svtypes_layered_randomize_active();
    return __svtypes_layered_randomize_active;
  endfunction
  function int svtypes_layered_randomize_priority();
    return __svtypes_layered_randomize_priority;
  endfunction

  virtual function int layered_randomize();
    int __svtypes_ok;
    bit __svtypes_previous_layered_active;
    int __svtypes_previous_layered_priority;
    int __svtypes_rand_finished;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_finished = finished.rand_mode();
    finished.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      finished.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        finished.rand_mode(0);
      end
    end
    finished.rand_mode(__svtypes_rand_finished);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 1);
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
    __svtypes_key = (prefix == "") ? "canonical_id=%s" : {prefix, ".canonical_id=%s"};
    if ($test$plusargs((prefix == "") ? "canonical_id" : {prefix, ".canonical_id"}) && !$value$plusargs(__svtypes_key, canonical_id)) $fatal(2, "Malformed plusarg canonical_id");
    __svtypes_key = (prefix == "") ? "factory_name=%s" : {prefix, ".factory_name=%s"};
    if ($test$plusargs((prefix == "") ? "factory_name" : {prefix, ".factory_name"}) && !$value$plusargs(__svtypes_key, factory_name)) $fatal(2, "Malformed plusarg factory_name");
    __svtypes_key = (prefix == "") ? "sv_base=%s" : {prefix, ".sv_base=%s"};
    if ($test$plusargs((prefix == "") ? "sv_base" : {prefix, ".sv_base"}) && !$value$plusargs(__svtypes_key, sv_base)) $fatal(2, "Malformed plusarg sv_base");
    __svtypes_key = (prefix == "") ? "finished=%h" : {prefix, ".finished=%h"};
    if ($test$plusargs((prefix == "") ? "finished" : {prefix, ".finished"}) && !$value$plusargs(__svtypes_key, finished)) $fatal(2, "Malformed plusarg finished");
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
    result = $sformatf("UvmxRegistration#%0d{", __svtypes_object_number);
    result = {result, "canonical_id="};
    result = {result, svtypes_pkg::escape_dump_string(this.canonical_id)};
    result = {result, ", factory_name="};
    result = {result, svtypes_pkg::escape_dump_string(this.factory_name)};
    result = {result, ", sv_base="};
    result = {result, svtypes_pkg::escape_dump_string(this.sv_base)};
    result = {result, ", finished="};
    result = {result, $sformatf("%0h", this.finished)};
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
    svtypes_pkg::pack_object_header("uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 4, __svtypes_object_number, bytes);
    svtypes_pkg::string_packer::pack(canonical_id, bytes);
    svtypes_pkg::string_packer::pack(factory_name, bytes);
    svtypes_pkg::string_packer::pack(sv_base, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(finished, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing UvmxRegistration object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing UvmxRegistration object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 4, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::string_packer::unpack(canonical_id, bytes, offset);
    svtypes_pkg::string_packer::unpack(factory_name, bytes, offset);
    svtypes_pkg::string_packer::unpack(sv_base, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(finished, bytes, offset);
  endfunction
endclass

// SvTypes typed channel helpers
task automatic svx_get_UvmxRegistration(string channel_name, output UvmxRegistration item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "UvmxRegistration", "uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 1, "svx_get_UvmxRegistration", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_UvmxRegistration", channel_name, "UvmxRegistration", offset, bytes.size());
endtask

task automatic svx_peek_UvmxRegistration(string channel_name, output UvmxRegistration item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "UvmxRegistration", "uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 1, "svx_peek_UvmxRegistration", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_UvmxRegistration", channel_name, "UvmxRegistration", offset, bytes.size());
endtask

task automatic svx_put_UvmxRegistration(string channel_name, input UvmxRegistration item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_UvmxRegistration(%s): cannot put null SvTypes object type UvmxRegistration", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "UvmxRegistration", "application/x-svtypes", "uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 1);
endtask

task automatic svx_try_get_UvmxRegistration(string channel_name, output bit ok, output UvmxRegistration item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "UvmxRegistration", "uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 1, "svx_try_get_UvmxRegistration", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_UvmxRegistration", channel_name, "UvmxRegistration", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_UvmxRegistration(string channel_name, input UvmxRegistration item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_UvmxRegistration(%s): cannot put null SvTypes object type UvmxRegistration", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "UvmxRegistration", "application/x-svtypes", "uvmx.UvmxRegistration", "b70c8936c726cbd8efe21b2b3d68e2e7d01eb90f8ea5eda6e72fbe858f55c1ce", 1);
endfunction
