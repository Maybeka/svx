`ifndef SVX_INHERITANCE__SV
`define SVX_INHERITANCE__SV

interface class svx_dispatchable;
  pure virtual task svx_invoke(
    string method_id,
    input chandle request,
    output bit ok,
    output chandle response,
    output string error
  );
endclass

interface class svx_factory;
  pure virtual task svx_create(
    longint unsigned object_id,
    input chandle request,
    output bit ok,
    output string error
  );
endclass

interface class svx_static_dispatchable;
  pure virtual task svx_invoke_static(
    string method_id,
    input chandle request,
    output bit ok,
    output chandle response,
    output string error
  );
endclass

// Internal framing for SVX's generated projected-field endpoints. The path
// and operation originate in SvTypes' public ExternalFieldStorage protocol;
// this class only carries them across the existing byte dispatcher.
class svx_field_operation;
  byte unsigned code;
  byte unsigned path_kind[$];
  string path_member[$];
  longint unsigned path_index[$];
  byte unsigned path_key[$][$];
  bit has_payload;
  byte unsigned payload[$];
endclass

function automatic bit svx_field_take_u32(
  ref byte unsigned bytes[$], ref int offset, output int unsigned value, input string what,
  output string error
);
  value = 0;
  if (offset < 0 || offset + 4 > bytes.size()) begin
    error = {"truncated ", what};
    return 0;
  end
  for (int i = 0; i < 4; i++) begin
    value |= int'(bytes[offset + i]) << (8 * i);
  end
  offset += 4;
  return 1;
endfunction

function automatic bit svx_field_take_bytes(
  ref byte unsigned bytes[$], ref int offset, input int unsigned count,
  ref byte unsigned value[$], input string what, output string error
);
  value.delete();
  if (count > bytes.size() || offset < 0 || offset + count > bytes.size()) begin
    error = {"truncated ", what};
    return 0;
  end
  for (int unsigned i = 0; i < count; i++) begin
    value.push_back(bytes[offset + i]);
  end
  offset += count;
  return 1;
endfunction

function automatic bit svx_field_operation_unpack(
  ref byte unsigned bytes[$], output svx_field_operation operation, output string error
);
  int offset;
  int unsigned path_count;
  int unsigned count;
  byte unsigned item[$];
  operation = new();
  error = "";
  offset = 0;
  if (bytes.size() < 10 || bytes[0] != "S" || bytes[1] != "V" ||
      bytes[2] != "X" || bytes[3] != "F" || bytes[4] != 1) begin
    error = "invalid SVX projected-field operation envelope";
    return 0;
  end
  operation.code = bytes[5];
  offset = 6;
  if (!svx_field_take_u32(bytes, offset, path_count, "field path length", error)) return 0;
  for (int unsigned segment = 0; segment < path_count; segment++) begin
    if (offset >= bytes.size()) begin
      error = "truncated field path segment kind";
      return 0;
    end
    operation.path_kind.push_back(bytes[offset]);
    offset++;
    if (!svx_field_take_u32(bytes, offset, count, "field path segment", error)) return 0;
    if (!svx_field_take_bytes(bytes, offset, count, item, "field path segment", error)) return 0;
    case (operation.path_kind[segment])
      1: begin
        string member;
        member = "";
        foreach (item[i]) member = {member, item[i]};
        operation.path_member.push_back(member);
        operation.path_index.push_back(0);
        operation.path_key.push_back({});
      end
      2: begin
        longint unsigned index;
        if (item.size() != 8) begin
          error = "field index segment must have eight bytes";
          return 0;
        end
        index = 0;
        foreach (item[i]) index |= longint'(item[i]) << (8 * i);
        operation.path_member.push_back("");
        operation.path_index.push_back(index);
        operation.path_key.push_back({});
      end
      3: begin
        operation.path_member.push_back("");
        operation.path_index.push_back(0);
        operation.path_key.push_back(item);
      end
      default: begin
        error = "unknown SVX projected-field path segment kind";
        return 0;
      end
    endcase
  end
  if (offset >= bytes.size()) begin
    error = "truncated field payload marker";
    return 0;
  end
  operation.has_payload = bytes[offset] != 0;
  offset++;
  if (operation.has_payload) begin
    if (!svx_field_take_u32(bytes, offset, count, "field payload length", error)) return 0;
    if (!svx_field_take_bytes(bytes, offset, count, operation.payload, "field payload", error)) return 0;
  end
  if (offset != bytes.size()) begin
    error = "trailing bytes in SVX projected-field operation envelope";
    return 0;
  end
  return 1;
endfunction

class svx_inheritance_registry;
  static svx_dispatchable objects[longint unsigned];
  static svx_static_dispatchable static_objects[string];
  static svx_factory factories[string];
  static longint unsigned next_object_id = 1;

  static function longint unsigned allocate_object_id();
    longint unsigned object_id = next_object_id;
    next_object_id++;
    if (object_id == 0) begin
      object_id = next_object_id;
      next_object_id++;
    end
    return object_id;
  endfunction

  static function void register_object(longint unsigned object_id, svx_dispatchable object);
    if (object_id == 0) begin
      $fatal(2, "SVX inheritance object id 0 is reserved");
    end
    if (object == null) begin
      $fatal(2, "SVX inheritance cannot bind a null dispatchable object");
    end
    if (objects.exists(object_id)) begin
      $fatal(2, "SVX inheritance object id %0d is already bound", object_id);
    end
    objects[object_id] = object;
  endfunction

  static function void unbind(longint unsigned object_id);
    objects.delete(object_id);
  endfunction

  static function void clear();
    objects.delete();
    static_objects.delete();
    factories.delete();
  endfunction

  static function void register_factory(string class_id, svx_factory factory);
    if (factory == null) begin
      $fatal(2, "SVX cannot register a null factory for %s", class_id);
    end
    factories[class_id] = factory;
  endfunction

  static function void register_static(string class_id, svx_static_dispatchable object);
    if (object == null) begin
      $fatal(2, "SVX cannot register a null static dispatcher for %s", class_id);
    end
    static_objects[class_id] = object;
  endfunction
endclass

task automatic svx_create_object(
  string class_id,
  input chandle request,
  output bit ok,
  output longint unsigned object_id,
  output string error
);
  object_id = 0;
  if (!svx_inheritance_registry::factories.exists(class_id)) begin
    ok = 0;
    error = {"no SVX factory registered for ", class_id};
    return;
  end
  object_id = svx_inheritance_registry::allocate_object_id();
  svx_inheritance_registry::factories[class_id].svx_create(object_id, request, ok, error);
  if (!ok) begin
    svx_inheritance_registry::unbind(object_id);
    object_id = 0;
  end
endtask

task automatic svx_invoke_object(
  longint unsigned object_id,
  string method_id,
  input chandle request,
  output bit ok,
  output chandle response,
  output string error
);
  response = null;
  if (!svx_inheritance_registry::objects.exists(object_id)) begin
    ok = 0;
    error = $sformatf("SVX1|unknown_object|%0d|%s|unknown SVX inheritance object id %0d",
                      object_id, method_id, object_id);
    return;
  end
  svx_inheritance_registry::objects[object_id].svx_invoke(
    method_id, request, ok, response, error
  );
  if (!ok && error.substr(0, 4) != "SVX1|") begin
    error = $sformatf("SVX1|dispatch_failed|%0d|%s|%s",
                      object_id, method_id, error);
  end
endtask

task automatic svx_invoke_static(
  string class_id,
  string method_id,
  input chandle request,
  output bit ok,
  output chandle response,
  output string error
);
  response = null;
  if (!svx_inheritance_registry::static_objects.exists(class_id)) begin
    ok = 0;
    error = {"SVX1|unknown_static_class|0|", method_id,
             "|no SVX static dispatcher registered for ", class_id};
    return;
  end
  svx_inheritance_registry::static_objects[class_id].svx_invoke_static(
    method_id, request, ok, response, error
  );
  if (!ok && error.substr(0, 4) != "SVX1|") begin
    error = $sformatf("SVX1|dispatch_failed|0|%s|%s", method_id, error);
  end
endtask

import "DPI-C" context task svx_inheritance_call_python(
  longint unsigned object_id,
  string method_id,
  input chandle request,
  output bit ok,
  output chandle response,
  output string error
);

import "DPI-C" context function chandle svx_inheritance_call_python_function(
  longint unsigned object_id,
  string method_id,
  input chandle request,
  output bit ok,
  output string error
);

import "DPI-C" context task svx_inheritance_shutdown();

import "DPI-C" context task svx_inheritance_release_python(
  longint unsigned object_id,
  output bit ok,
  output string error
);

import "DPI-C" context task svx_inheritance_create_python(
  string class_id,
  longint unsigned object_id,
  input chandle request,
  output bit ok,
  output string error
);

task automatic svx_release_object(longint unsigned object_id);
  bit ok;
  string error;
  // Retire Python-owned field bindings while the paired SV object is still
  // registered. A failed retirement must not leave stale field access alive.
  svx_inheritance_release_python(object_id, ok, error);
  if (!ok) begin
    $fatal(2, "SVX inheritance release %0d failed: %s", object_id, error);
  end
  svx_inheritance_registry::unbind(object_id);
endtask

task automatic svx_shutdown();
  svx_inheritance_registry::clear();
  svx_inheritance_shutdown();
  svx_channel_registry::clear();
  svx_runtime_shutdown();
endtask

export "DPI-C" task svx_invoke_object;
export "DPI-C" task svx_invoke_static;
export "DPI-C" task svx_release_object;
export "DPI-C" task svx_create_object;

`endif
