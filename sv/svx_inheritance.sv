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

class svx_inheritance_registry;
  static svx_dispatchable objects[longint unsigned];
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
    factories.delete();
  endfunction

  static function void register_factory(string class_id, svx_factory factory);
    if (factory == null) begin
      $fatal(2, "SVX cannot register a null factory for %s", class_id);
    end
    factories[class_id] = factory;
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

task automatic svx_release_object(longint unsigned object_id);
  svx_inheritance_registry::unbind(object_id);
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

import "DPI-C" context task svx_inheritance_create_python(
  string class_id,
  longint unsigned object_id,
  input chandle request,
  output bit ok,
  output string error
);

task automatic svx_shutdown();
  svx_inheritance_registry::clear();
  svx_inheritance_shutdown();
  svx_channel_registry::clear();
  svx_runtime_shutdown();
endtask

export "DPI-C" task svx_invoke_object;
export "DPI-C" task svx_release_object;
export "DPI-C" task svx_create_object;

`endif
