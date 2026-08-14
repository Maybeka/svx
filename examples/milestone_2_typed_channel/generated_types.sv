// Generated from examples.milestone_2_typed_channel.tests.typed_test
// Do not edit by hand.

package m2_typed_pkg;

  typedef class M2Transaction;

  class M2Transaction extends svtypes_pkg::sv_object;
    rand bit [15:0] addr;
    rand int data;

    static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
      svtypes_pkg::encoding_descriptor descriptor;
      descriptor = new("tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 1);
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
      __svtypes_key = (prefix == "") ? "addr=%h" : {prefix, ".addr=%h"};
      if ($test$plusargs((prefix == "") ? "addr" : {prefix, ".addr"}) && !$value$plusargs(__svtypes_key, addr)) $fatal(2, "Malformed plusarg addr");
      __svtypes_key = (prefix == "") ? "data=%d" : {prefix, ".data=%d"};
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
      result = $sformatf("M2Transaction#%0d{", __svtypes_object_number);
      result = {result, "addr="};
      result = {result, $sformatf("%0h", addr)};
      result = {result, ", data="};
      result = {result, $sformatf("%0d", data)};
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
      svtypes_pkg::pack_object_header("tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 2, __svtypes_object_number, bytes);
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
      longint unsigned incoming_svtypes_object_number;
      svtypes_pkg::unpack_object_header("tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 2, incoming_svtypes_object_number, bytes, offset);
      __svtypes_object_number = incoming_svtypes_object_number;
      svtypes_pkg::register_object(this);
      svtypes_pkg::bits_packer#(bit [15:0])::unpack(addr, bytes, offset);
      svtypes_pkg::int_packer::unpack(data, bytes, offset);
    endfunction
  endclass

  class M2Transaction__svtypes_coverage;
    covergroup cg with function sample(M2Transaction item);
      option.per_instance = 1;
      addr_cp: coverpoint item.addr;
      data_cp: coverpoint item.data;
    endgroup

    function new();
      cg = new();
    endfunction

    function void sample(M2Transaction item);
      cg.sample(item);
    endfunction
  endclass

  // SvTypes typed channel helpers
  task automatic svx_get_M2Transaction(string channel_name, output M2Transaction item);
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    svx_pkg::svx_channel_get_payload(channel_name, payload);
    svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M2Transaction", "tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 1, "svx_get_M2Transaction", bytes);
    svx_pkg::svx_payload_destroy(payload);
    item = new();
    offset = 0;
    item.unpack(bytes, offset);
    svx_pkg::svx_require_unpacked_all("svx_get_M2Transaction", channel_name, "M2Transaction", offset, bytes.size());
  endtask

  task automatic svx_peek_M2Transaction(string channel_name, output M2Transaction item);
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    svx_pkg::svx_channel_peek_payload(channel_name, payload);
    svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M2Transaction", "tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 1, "svx_peek_M2Transaction", bytes);
    item = new();
    offset = 0;
    item.unpack(bytes, offset);
    svx_pkg::svx_require_unpacked_all("svx_peek_M2Transaction", channel_name, "M2Transaction", offset, bytes.size());
  endtask

  task automatic svx_put_M2Transaction(string channel_name, input M2Transaction item);
    byte unsigned bytes[$];
    if (item == null) begin
      $fatal(2, "svx_put_M2Transaction(%s): cannot put null SvTypes object type M2Transaction", channel_name);
    end
    item.pack(bytes);
    svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M2Transaction", "application/x-svtypes", "tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 1);
  endtask

  task automatic svx_try_get_M2Transaction(string channel_name, output bit ok, output M2Transaction item);
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    payload = svx_pkg::svx_channel_try_get_payload(channel_name);
    if (payload == null) begin
      ok = 0;
      item = null;
      return;
    end
    svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M2Transaction", "tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 1, "svx_try_get_M2Transaction", bytes);
    svx_pkg::svx_payload_destroy(payload);
    item = new();
    offset = 0;
    item.unpack(bytes, offset);
    svx_pkg::svx_require_unpacked_all("svx_try_get_M2Transaction", channel_name, "M2Transaction", offset, bytes.size());
    ok = 1;
  endtask

  function automatic bit svx_try_put_M2Transaction(string channel_name, input M2Transaction item);
    byte unsigned bytes[$];
    if (item == null) begin
      $fatal(2, "svx_try_put_M2Transaction(%s): cannot put null SvTypes object type M2Transaction", channel_name);
    end
    item.pack(bytes);
    return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M2Transaction", "application/x-svtypes", "tests.M2Transaction", "e06dff90065925826541e2776bc731af03fff5911a5f9bd00d427d1157c3e754", 1);
  endfunction

endpackage : m2_typed_pkg
