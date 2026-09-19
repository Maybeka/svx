`ifndef SVX_CHANNEL__SV
`define SVX_CHANNEL__SV

import "DPI-C" context function chandle svx_payload_create(
  string kind,
  string type_name,
  string content_type
);
import "DPI-C" context function void svx_payload_push_byte(chandle payload, byte unsigned value);
import "DPI-C" context function int svx_payload_size(chandle payload);
import "DPI-C" context function byte unsigned svx_payload_get_byte(chandle payload, int index);
import "DPI-C" context function string svx_payload_kind(chandle payload);
import "DPI-C" context function string svx_payload_type_name(chandle payload);
import "DPI-C" context function string svx_payload_content_type(chandle payload);
import "DPI-C" context function string svx_payload_unified_type_name(chandle payload);
import "DPI-C" context function string svx_payload_encoding_fingerprint(chandle payload);
import "DPI-C" context function int unsigned svx_payload_binary_format_version(chandle payload);
import "DPI-C" context function void svx_payload_set_encoding_descriptor(
  chandle payload,
  string unified_type_name,
  string encoding_fingerprint,
  int unsigned binary_format_version
);
import "DPI-C" context function void svx_payload_destroy(chandle payload);

class svx_channel;
  mailbox #(chandle) fifo = new(SVX_CHANNEL_CAPACITY);
  bit binding_set = 0;
  string bound_kind;
  string bound_content_type;
  string bound_unified_type_name;
  string bound_encoding_fingerprint;
  int unsigned bound_binary_format_version;

  function void require_compatible(string name, chandle payload);
    string kind;
    string content_type;
    string unified_type_name;
    string encoding_fingerprint;
    int unsigned binary_format_version;
    if (payload == null) begin
      $fatal(2, "SVX channel %s cannot accept a null payload", name);
    end
    kind = svx_payload_kind(payload);
    content_type = svx_payload_content_type(payload);
    unified_type_name = svx_payload_unified_type_name(payload);
    encoding_fingerprint = svx_payload_encoding_fingerprint(payload);
    binary_format_version = svx_payload_binary_format_version(payload);
    if (!binding_set) begin
      binding_set = 1;
      bound_kind = kind;
      bound_content_type = content_type;
      bound_unified_type_name = unified_type_name;
      bound_encoding_fingerprint = encoding_fingerprint;
      bound_binary_format_version = binary_format_version;
      return;
    end
    if (kind != bound_kind || content_type != bound_content_type ||
        unified_type_name != bound_unified_type_name ||
        encoding_fingerprint != bound_encoding_fingerprint ||
        binary_format_version != bound_binary_format_version) begin
      $fatal(2,
        "SVX channel %s payload type conflicts with its first-use binding (%s, %s, %s, %s, %0d)",
        name, bound_kind, bound_content_type, bound_unified_type_name,
        bound_encoding_fingerprint, bound_binary_format_version);
    end
  endfunction

  task put(string name, chandle payload);
    require_compatible(name, payload);
    fifo.put(payload);
  endtask

  task get(output chandle payload);
    fifo.get(payload);
  endtask

  task peek(output chandle payload);
    fifo.peek(payload);
  endtask

  function bit try_put(string name, chandle payload);
    require_compatible(name, payload);
    return fifo.try_put(payload);
  endfunction

  function bit try_get(output chandle payload);
    return fifo.try_get(payload);
  endfunction

  function void clear();
    chandle payload;
    while (fifo.try_get(payload)) begin
      if (payload != null) begin
        svx_payload_destroy(payload);
      end
    end
    binding_set = 0;
    bound_kind = "";
    bound_content_type = "";
    bound_unified_type_name = "";
    bound_encoding_fingerprint = "";
    bound_binary_format_version = 0;
  endfunction
endclass

class svx_channel_registry;
  static svx_channel channels[string];

  static function svx_channel get(string name);
    if (!channels.exists(name)) begin
      channels[name] = new();
    end
    return channels[name];
  endfunction


  static function void clear();
    foreach (channels[name]) begin
      channels[name].clear();
    end
    channels.delete();
  endfunction
endclass

task automatic svx_channel_put_payload(string name, chandle payload, int process_index,
                                       output bit cancelled);
  cancelled = 0;
  if (process_index < 0) begin
    svx_channel_registry::get(name).put(name, payload);
    return;
  end
  fork : svx_channel_put_wait
    svx_channel_registry::get(name).put(name, payload);
    begin
      svx_proc_man::wait_for_cancel(process_index);
      cancelled = 1;
    end
  join_any
  disable svx_channel_put_wait;
endtask

task automatic svx_channel_get_payload(string name, int process_index,
                                       output chandle payload, output bit cancelled);
  cancelled = 0;
  payload = null;
  if (process_index < 0) begin
    svx_channel_registry::get(name).get(payload);
    return;
  end
  fork : svx_channel_get_wait
    svx_channel_registry::get(name).get(payload);
    begin
      svx_proc_man::wait_for_cancel(process_index);
      cancelled = 1;
    end
  join_any
  disable svx_channel_get_wait;
endtask

task automatic svx_channel_peek_payload(string name, int process_index,
                                        output chandle payload, output bit cancelled);
  cancelled = 0;
  payload = null;
  if (process_index < 0) begin
    svx_channel_registry::get(name).peek(payload);
    return;
  end
  fork : svx_channel_peek_wait
    svx_channel_registry::get(name).peek(payload);
    begin
      svx_proc_man::wait_for_cancel(process_index);
      cancelled = 1;
    end
  join_any
  disable svx_channel_peek_wait;
endtask

function automatic bit svx_channel_try_put_payload(string name, chandle payload);
  return svx_channel_registry::get(name).try_put(name, payload);
endfunction

function automatic chandle svx_channel_try_get_payload(string name);
  chandle payload;
  if (!svx_channel_registry::get(name).try_get(payload)) begin
    return null;
  end
  return payload;
endfunction

function automatic chandle svx_payload_from_bytes(
  byte unsigned data[],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream"
);
  chandle payload;
  if (data.size() > SVX_MAX_PAYLOAD_BYTES) begin
    $fatal(2, "SVX payload has %0d bytes; limit is %0d",
      data.size(), SVX_MAX_PAYLOAD_BYTES);
  end
  payload = svx_payload_create(kind, type_name, content_type);
  foreach (data[i]) begin
    svx_payload_push_byte(payload, data[i]);
  end
  return payload;
endfunction

function automatic chandle svx_payload_from_byte_queue(
  byte unsigned data[$],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream"
);
  chandle payload;
  if (data.size() > SVX_MAX_PAYLOAD_BYTES) begin
    $fatal(2, "SVX payload has %0d bytes; limit is %0d",
      data.size(), SVX_MAX_PAYLOAD_BYTES);
  end
  payload = svx_payload_create(kind, type_name, content_type);
  foreach (data[i]) begin
    svx_payload_push_byte(payload, data[i]);
  end
  return payload;
endfunction

function automatic void svx_payload_to_byte_queue(
  chandle payload,
  ref byte unsigned data[$]
);
  data.delete();
  for (int i = 0; i < svx_payload_size(payload); i++) begin
    data.push_back(svx_payload_get_byte(payload, i));
  end
endfunction

function automatic void svx_require_svtypes_payload(
  chandle payload,
  string channel_name,
  string expected_type,
  string helper_name = "svx_require_svtypes_payload"
);
  string actual_kind;
  string actual_type;
  string actual_content_type;

  if (payload == null) begin
    $fatal(2, "%s(%s): expected SvTypes payload type %s, got null payload",
      helper_name, channel_name, expected_type);
  end

  actual_kind = svx_payload_kind(payload);
  actual_type = svx_payload_type_name(payload);
  actual_content_type = svx_payload_content_type(payload);

  if (actual_kind != "svtypes") begin
    $fatal(2, "%s(%s): expected SvTypes payload kind svtypes for type %s, got %s",
      helper_name, channel_name, expected_type, actual_kind);
  end
  if (actual_content_type != "application/x-svtypes") begin
    $fatal(2, "%s(%s): expected SvTypes content type application/x-svtypes for type %s, got %s",
      helper_name, channel_name, expected_type, actual_content_type);
  end
  if (actual_type != "" && actual_type != expected_type) begin
    $fatal(2, "%s(%s): expected SvTypes payload type %s, got %s",
      helper_name, channel_name, expected_type, actual_type);
  end
endfunction

function automatic void svx_require_svtypes_wire_payload(
  chandle payload,
  string channel_name,
  string expected_type,
  string expected_unified_type_name,
  string expected_encoding_fingerprint,
  int unsigned expected_binary_format_version,
  string helper_name = "svx_require_svtypes_payload"
);
  svx_require_svtypes_payload(payload, channel_name, expected_type, helper_name);
  if (svx_payload_unified_type_name(payload) != expected_unified_type_name) begin
    $fatal(2, "%s(%s): expected SvTypes unified type name %s, got %s",
      helper_name, channel_name, expected_unified_type_name,
      svx_payload_unified_type_name(payload));
  end
  if (svx_payload_encoding_fingerprint(payload) != expected_encoding_fingerprint) begin
    $fatal(2, "%s(%s): SvTypes encoding fingerprint mismatch for %s",
      helper_name, channel_name, expected_unified_type_name);
  end
  if (svx_payload_binary_format_version(payload) != expected_binary_format_version) begin
    $fatal(2, "%s(%s): expected SvTypes binary format %0d, got %0d",
      helper_name, channel_name, expected_binary_format_version,
      svx_payload_binary_format_version(payload));
  end
endfunction

function automatic void svx_payload_to_checked_byte_queue(
  chandle payload,
  string channel_name,
  string expected_type,
  string expected_unified_type_name,
  string expected_encoding_fingerprint,
  int unsigned expected_binary_format_version,
  string helper_name,
  ref byte unsigned data[$]
);
  svx_require_svtypes_wire_payload(
    payload, channel_name, expected_type, expected_unified_type_name,
    expected_encoding_fingerprint, expected_binary_format_version, helper_name
  );
  svx_payload_to_byte_queue(payload, data);
endfunction

function automatic void svx_require_unpacked_all(
  string helper_name,
  string channel_name,
  string expected_type,
  int offset,
  int size
);
  if (offset != size) begin
    $fatal(2, "%s(%s): unpacked SvTypes payload type %s consumed %0d of %0d bytes",
      helper_name, channel_name, expected_type, offset, size);
  end
endfunction

task automatic svx_channel_put_bytes(
  string name,
  byte unsigned data[],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream"
);
  chandle payload = svx_payload_from_bytes(data, kind, type_name, content_type);
  bit cancelled;
  svx_channel_put_payload(name, payload, -1, cancelled);
endtask

task automatic svx_channel_put_byte_queue(
  string name,
  byte unsigned data[$],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream",
  string unified_type_name = "",
  string encoding_fingerprint = "",
  int unsigned binary_format_version = 0
);
  chandle payload = svx_payload_from_byte_queue(data, kind, type_name, content_type);
  bit cancelled;
  if (unified_type_name != "") begin
    svx_payload_set_encoding_descriptor(
      payload, unified_type_name, encoding_fingerprint, binary_format_version
    );
  end
  svx_channel_put_payload(name, payload, -1, cancelled);
endtask

function automatic bit svx_channel_try_put_bytes(
  string name,
  byte unsigned data[],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream"
);
  chandle payload = svx_payload_from_bytes(data, kind, type_name, content_type);
  if (!svx_channel_try_put_payload(name, payload)) begin
    svx_payload_destroy(payload);
    return 0;
  end
  return 1;
endfunction

function automatic bit svx_channel_try_put_byte_queue(
  string name,
  byte unsigned data[$],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream",
  string unified_type_name = "",
  string encoding_fingerprint = "",
  int unsigned binary_format_version = 0
);
  chandle payload = svx_payload_from_byte_queue(data, kind, type_name, content_type);
  if (unified_type_name != "") begin
    svx_payload_set_encoding_descriptor(
      payload, unified_type_name, encoding_fingerprint, binary_format_version
    );
  end
  if (!svx_channel_try_put_payload(name, payload)) begin
    svx_payload_destroy(payload);
    return 0;
  end
  return 1;
endfunction

export "DPI-C" task svx_channel_put_payload;
export "DPI-C" task svx_channel_get_payload;
export "DPI-C" task svx_channel_peek_payload;
export "DPI-C" function svx_channel_try_put_payload;
export "DPI-C" function svx_channel_try_get_payload;

`endif
