`ifndef UVMX_BRIDGE__SV
`define UVMX_BRIDGE__SV

// This bridge only adapts UVM's factory/phase API to the existing generated
// SVX inheritance lifecycle.  UVMX owns no scheduler, objection system, or
// alternate component hierarchy.
function automatic longint unsigned uvmx_bridge_bind(
  string class_id,
  svx_dispatchable proxy
);
  longint unsigned object_id;
  chandle request;
  string error;
  byte unsigned bytes[$];

  object_id = svx_inheritance_registry::allocate_object_id();
  svx_inheritance_registry::register_object(object_id, proxy);
  request = svx_payload_from_byte_queue(
    bytes, "svx-inheritance", "", "application/x-svx-inheritance"
  );
  if (!svx_inheritance_create_python_function(class_id, object_id, request, error)) begin
    svx_payload_destroy(request);
    svx_inheritance_registry::unbind(object_id);
    $fatal(2, "UVMX construction %s failed: %s", class_id, error);
  end
  svx_payload_destroy(request);
  return object_id;
endfunction

function automatic void uvmx_bridge_call_function(
  longint unsigned object_id,
  string method_id
);
  bit ok;
  chandle request;
  chandle response;
  string error;
  byte unsigned bytes[$];

  request = svx_payload_from_byte_queue(
    bytes, "svx-inheritance", "", "application/x-svx-inheritance"
  );
  response = svx_inheritance_call_python_function(object_id, method_id, request, ok, error);
  svx_payload_destroy(request);
  if (response != null) svx_payload_destroy(response);
  if (!ok) begin
    $fatal(2, "UVMX function callback %s for object %0d failed: %s", method_id, object_id, error);
  end
endfunction

task automatic uvmx_bridge_call_task(
  longint unsigned object_id,
  string method_id
);
  bit ok;
  chandle request;
  chandle response;
  string error;
  byte unsigned bytes[$];

  request = svx_payload_from_byte_queue(
    bytes, "svx-inheritance", "", "application/x-svx-inheritance"
  );
  svx_inheritance_call_python(object_id, method_id, request, ok, response, error);
  svx_payload_destroy(request);
  if (response != null) svx_payload_destroy(response);
  if (!ok) begin
    $fatal(2, "UVMX task callback %s for object %0d failed: %s", method_id, object_id, error);
  end
endtask

task automatic uvmx_run_test(string python_module, string explicit_test_name = "");
  string alias_name;
  string canonical_name;

  svx_init();
  svx_load(python_module);
  uvm_top.finish_on_completion = 0;

  if ($value$plusargs("UVM_TESTNAME=%s", canonical_name)) begin
    uvm_pkg::run_test();
  end else if ($value$plusargs("UVM_TEST_NAME=%s", alias_name)) begin
    `uvm_warning("UVMX/TESTNAME", "use +UVM_TESTNAME, not +UVM_TEST_NAME")
    uvm_pkg::run_test(alias_name);
  end else begin
    uvm_pkg::run_test(explicit_test_name);
  end

  svx_shutdown();
  $finish;
endtask

`endif
