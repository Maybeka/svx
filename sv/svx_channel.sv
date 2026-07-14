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
import "DPI-C" context function void svx_payload_destroy(chandle payload);

class svx_channel;
  mailbox #(chandle) fifo = new();

  task put(chandle payload);
    fifo.put(payload);
  endtask

  task get(output chandle payload);
    fifo.get(payload);
  endtask

  task peek(output chandle payload);
    fifo.peek(payload);
  endtask

  function bit try_put(chandle payload);
    return fifo.try_put(payload);
  endfunction

  function bit try_get(output chandle payload);
    return fifo.try_get(payload);
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
endclass

task automatic svx_channel_put_payload(string name, chandle payload);
  svx_channel_registry::get(name).put(payload);
endtask

task automatic svx_channel_get_payload(string name, output chandle payload);
  svx_channel_registry::get(name).get(payload);
endtask

task automatic svx_channel_peek_payload(string name, output chandle payload);
  svx_channel_registry::get(name).peek(payload);
endtask

function automatic bit svx_channel_try_put_payload(string name, chandle payload);
  return svx_channel_registry::get(name).try_put(payload);
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
  chandle payload = svx_payload_create(kind, type_name, content_type);
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
  chandle payload = svx_payload_create(kind, type_name, content_type);
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

function automatic void svx_payload_to_checked_byte_queue(
  chandle payload,
  string channel_name,
  string expected_type,
  string helper_name,
  ref byte unsigned data[$]
);
  svx_require_svtypes_payload(payload, channel_name, expected_type, helper_name);
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
  svx_channel_put_payload(name, payload);
endtask

task automatic svx_channel_put_byte_queue(
  string name,
  byte unsigned data[$],
  string kind = "bytes",
  string type_name = "",
  string content_type = "application/octet-stream"
);
  chandle payload = svx_payload_from_byte_queue(data, kind, type_name, content_type);
  svx_channel_put_payload(name, payload);
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
  string content_type = "application/octet-stream"
);
  chandle payload = svx_payload_from_byte_queue(data, kind, type_name, content_type);
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
