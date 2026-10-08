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

interface class svx_function_dispatchable;
  pure virtual function void svx_invoke_function(
    string method_id, input chandle request, output bit ok,
    output chandle response, output string error
  );
endclass

interface class svx_static_function_dispatchable;
  pure virtual function void svx_invoke_static_function(
    string method_id, input chandle request, output bit ok,
    output chandle response, output string error
  );
endclass

class svx_object_id_allocator;
  static longint unsigned next_object_id = 1;

  static function longint unsigned allocate();
    longint unsigned object_id = next_object_id;
    next_object_id++;
    if (object_id == 0) begin
      object_id = next_object_id;
      next_object_id++;
    end
    return object_id;
  endfunction
endclass

// A foreign handle is retained only through one generated, statically typed
// wrapper. The generic registry never sees the underlying class or virtual
// interface type, so it cannot accidentally cast a handle to an unrelated
// SV type.
interface class svx_external_handle;
  pure virtual function string svx_external_target_type();
endclass

interface class svx_session_resource;
  pure virtual function void clear_session();
endclass

class svx_external_handle_registry;
  static svx_external_handle objects[longint unsigned];
  static svx_session_resource resources[$];

  static function void register_resource(svx_session_resource resource);
    foreach (resources[index]) begin
      if (resources[index] == resource) return;
    end
    resources.push_back(resource);
  endfunction

  static function longint unsigned allocate_object_id();
    return svx_object_id_allocator::allocate();
  endfunction

  static function void register_object(
    longint unsigned object_id,
    svx_external_handle object
  );
    if (object_id == 0) begin
      $fatal(2, "SVX external handle object id 0 is reserved");
    end
    if (object == null) begin
      $fatal(2, "SVX cannot register a null external handle endpoint");
    end
    if (objects.exists(object_id)) begin
      $fatal(2, "SVX external handle object id %0d is already bound", object_id);
    end
    objects[object_id] = object;
  endfunction

  static function bit resolve(
    longint unsigned object_id,
    string target_type_name,
    output svx_external_handle object,
    output string error
  );
    object = null;
    error = "";
    if (object_id == 0) return 1;
    if (!objects.exists(object_id)) begin
      error = $sformatf("unknown external handle id %0d", object_id);
      return 0;
    end
    object = objects[object_id];
    if (object.svx_external_target_type() != target_type_name) begin
      error = $sformatf("external handle %0d has target %s, expected %s",
                        object_id, object.svx_external_target_type(), target_type_name);
      object = null;
      return 0;
    end
    return 1;
  endfunction

  static function void clear();
    foreach (resources[index]) resources[index].clear_session();
    resources.delete();
    objects.delete();
  endfunction
endclass

interface class svx_factory;
  pure virtual function void svx_create(
    longint unsigned object_id,
    input chandle request,
    output bit ok,
    output string error
  );
endclass

class svx_construction_frame;
  longint unsigned object_id;
  svx_dispatchable receiver;
  function new(longint unsigned id, svx_dispatchable value);
    object_id = id;
    receiver = value;
  endfunction
endclass

class svx_construction_context;
  static svx_construction_frame frames[$];

  static function bit enter(longint unsigned object_id, svx_dispatchable receiver);
    svx_construction_frame frame;
    if (receiver == null) $fatal(2, "SVX construction receiver is null");
    if (frames.size() != 0 && frames[$].receiver == receiver) begin
      if (object_id != 0 && frames[$].object_id != object_id)
        $fatal(2, "SVX inherited constructor changed the paired object ID");
      return 0;
    end
    frame = new(object_id, receiver);
    frames.push_back(frame);
    return 1;
  endfunction

  static function longint unsigned current_id(svx_dispatchable receiver);
    if (frames.size() == 0 || frames[$].receiver != receiver)
      $fatal(2, "SVX construction receiver is outside its context");
    return frames[$].object_id;
  endfunction

  static function void bind_id(svx_dispatchable receiver, longint unsigned object_id);
    if (frames.size() == 0 || frames[$].receiver != receiver || object_id == 0)
      $fatal(2, "SVX early construction receiver is outside its context");
    if (frames[$].object_id != 0 && frames[$].object_id != object_id)
      $fatal(2, "SVX early construction changed the paired object ID");
    frames[$].object_id = object_id;
  endfunction

  static function void leave(svx_dispatchable receiver, bit owned);
    svx_construction_frame frame;
    if (!owned) return;
    if (frames.size() == 0 || frames[$].receiver != receiver)
      $fatal(2, "SVX construction contexts returned out of order");
    frame = frames.pop_back();
  endfunction

  static function void retire_id(longint unsigned object_id);
    for (int index = frames.size() - 1; index >= 0; index--)
      if (frames[index].object_id == object_id) frames.delete(index);
  endfunction

  static function void clear();
    frames.delete();
  endfunction
endclass

virtual class svx_constructor_cache;
  pure virtual function void retire_receiver(longint unsigned receiver_id);
endclass

class svx_constructor_cache_registry;
  static svx_constructor_cache caches[$];

  static function void register_cache(svx_constructor_cache cache);
    foreach (caches[index]) if (caches[index] == cache) return;
    caches.push_back(cache);
  endfunction

  static function void retire_id(longint unsigned receiver_id);
    foreach (caches[index]) caches[index].retire_receiver(receiver_id);
  endfunction
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
  static longint unsigned published_object_ids[string];

  static function longint unsigned allocate_object_id();
    return svx_object_id_allocator::allocate();
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
    foreach (published_object_ids[name]) begin
      if (published_object_ids[name] == object_id) published_object_ids.delete(name);
    end
  endfunction

  static function void publish_object(string name, longint unsigned object_id);
    if (name.len() == 0) begin
      $fatal(2, "SVX published object name cannot be empty");
    end
    if (!objects.exists(object_id)) begin
      $fatal(2, "SVX cannot publish unknown inheritance object id %0d", object_id);
    end
    published_object_ids[name] = object_id;
  endfunction

  static function void require_published_object(
    string name,
    output svx_dispatchable object
  );
    longint unsigned object_id;
    object = null;
    if (!published_object_ids.exists(name)) begin
      $fatal(2, "SVX published object %s does not exist", name);
    end
    object_id = published_object_ids[name];
    if (!objects.exists(object_id)) begin
      published_object_ids.delete(name);
      $fatal(2, "SVX published object %s is no longer live", name);
    end
    object = objects[object_id];
  endfunction

  static function void clear();
    objects.delete();
    static_objects.delete();
    factories.delete();
    published_object_ids.delete();
    svx_construction_context::clear();
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

task automatic svx_publish_object(string name, longint unsigned object_id);
  svx_inheritance_registry::publish_object(name, object_id);
endtask

task automatic svx_require_published_object(
  string name,
  output svx_dispatchable object
);
  svx_inheritance_registry::require_published_object(name, object);
endtask

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

function automatic longint unsigned svx_create_object_function(
  string class_id, input chandle request, output bit ok, output string error
);
  longint unsigned object_id;
  ok = 0;
  if (!svx_inheritance_registry::factories.exists(class_id)) begin
    error = {"no SVX factory registered for ", class_id};
    return 0;
  end
  object_id = svx_inheritance_registry::allocate_object_id();
  svx_inheritance_registry::factories[class_id].svx_create(object_id, request, ok, error);
  if (!ok) begin
    svx_inheritance_registry::unbind(object_id);
    return 0;
  end
  return object_id;
endfunction

export "DPI-C" function svx_create_object_function;

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

function automatic chandle svx_invoke_object_function(
  longint unsigned object_id, string method_id, input chandle request,
  output bit ok, output string error
);
  svx_function_dispatchable object;
  chandle response;
  ok = 0;
  response = null;
  if (!svx_inheritance_registry::objects.exists(object_id)) begin
    error = $sformatf("SVX1|unknown_object|%0d|%s|unknown SVX inheritance object", object_id, method_id);
    return null;
  end
  if (!$cast(object, svx_inheritance_registry::objects[object_id])) begin
    error = $sformatf("SVX1|function_unavailable|%0d|%s|object has no function dispatcher", object_id, method_id);
    return null;
  end
  object.svx_invoke_function(method_id, request, ok, response, error);
  if (!ok && error.substr(0, 4) != "SVX1|")
    error = $sformatf("SVX1|dispatch_failed|%0d|%s|%s", object_id, method_id, error);
  return response;
endfunction

function automatic chandle svx_invoke_static_function(
  string class_id, string method_id, input chandle request,
  output bit ok, output string error
);
  svx_static_function_dispatchable object;
  chandle response;
  ok = 0;
  response = null;
  if (!svx_inheritance_registry::static_objects.exists(class_id)) begin
    error = {"SVX1|unknown_static_class|0|", method_id, "|unknown SVX static class"};
    return null;
  end
  if (!$cast(object, svx_inheritance_registry::static_objects[class_id])) begin
    error = {"SVX1|function_unavailable|0|", method_id, "|class has no function dispatcher"};
    return null;
  end
  object.svx_invoke_static_function(method_id, request, ok, response, error);
  if (!ok && error.substr(0, 4) != "SVX1|")
    error = $sformatf("SVX1|dispatch_failed|0|%s|%s", method_id, error);
  return response;
endfunction

export "DPI-C" function svx_invoke_object_function;
export "DPI-C" function svx_invoke_static_function;

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

import "DPI-C" context function bit svx_inheritance_release_python_function(
  longint unsigned object_id,
  output string error
);

import "DPI-C" context task svx_inheritance_create_python(
  string class_id,
  longint unsigned object_id,
  input chandle request,
  output bit ok,
  output string error
);

// Some SV-owned object models construct instances from a function context.
// The Python constructor bridge itself never advances simulation time, so a
// synchronous entry point is safe there.  The task entry above remains the
// general construction path for generated classes that are allowed to run in
// a task context.
import "DPI-C" context function bit svx_inheritance_create_python_function(
  string class_id,
  longint unsigned object_id,
  input chandle request,
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

function automatic void svx_release_object_function(longint unsigned object_id);
  bit ok;
  string error;
  ok = svx_inheritance_release_python_function(object_id, error);
  // Retire the SV registry even if a user cleanup hook failed.
  svx_inheritance_registry::unbind(object_id);
  svx_constructor_cache_registry::retire_id(object_id);
  svx_construction_context::retire_id(object_id);
  if (!ok) $fatal(2, "SVX inheritance release %0d failed: %s", object_id, error);
endfunction

task automatic svx_shutdown();
  svx_proc_man::shutdown();
  svx_inheritance_registry::clear();
  svx_external_handle_registry::clear();
  svx_inheritance_shutdown();
  svx_channel_registry::clear();
  svx_runtime_shutdown();
endtask

export "DPI-C" task svx_invoke_object;
export "DPI-C" task svx_invoke_static;
export "DPI-C" task svx_release_object;
export "DPI-C" function svx_release_object_function;
export "DPI-C" task svx_create_object;
export "DPI-C" task svx_publish_object;

`endif
