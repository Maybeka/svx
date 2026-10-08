`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "tests/integration/handle_collection_if.sv"
`include "tests/integration/handle_collection_types.sv"
`include ".tmp/handle_collection/mirrors.sv"

module tb;
  handle_collection_if first_bus();
  handle_collection_if second_bus();
  import svx_pkg::*;
  import handle_collection_pkg::*;
  Owner handle;
  svx_mirror_sv_handle_collection_pkg_ConstructorOwner::ConstructorOwner constructor_first;
  ConstructorOwner constructor_second;
  Item original;
  queue_t values, queue_result, observed, changed;
  dynamic_t dynamic_values, dynamic_result;
  fixed_t fixed_values, fixed_result;
  associative_t associative_values, associative_result;
  nested_t nested_values, nested_result;
  vif_queue_t vif_values, vif_result;
  vif_queue_t vif_observed, vif_changed;
  vif_dynamic_t vif_dynamic_values, vif_dynamic_result;
  vif_fixed_t vif_fixed_values, vif_fixed_result;
  vif_associative_t vif_associative_values, vif_associative_result;
  vif_nested_t vif_nested_values, vif_nested_result;
  initial begin
    svx_init();
    svx_load("tests.integration.handle_collection_test");
    original = new(91);
    values = '{original, null, original};
    nested_values["first"] = values;
    nested_values["empty"] = '{};
    vif_values = '{first_bus, null, second_bus, first_bus};
    constructor_first = new(values, nested_values, vif_values);
    svx_start("handle_collection.create");
    `SVX_GET_OBJECT(ConstructorOwner, "handle_collection.constructor", constructor_second)
    queue_result = constructor_second.get_items();
    nested_result = constructor_second.get_groups();
    constructor_second.get_ports(vif_result);
    if (ConstructorOwner::get_construction_count() != 2 || queue_result[0] != original ||
        queue_result[1] != null || queue_result[2] != original ||
        nested_result["first"][2] != original || nested_result["empty"].size() != 0 ||
        vif_result[0] != first_bus || vif_result[1] != null ||
        vif_result[2] != second_bus || vif_result[3] != first_bus)
      $fatal(1, "constructor collection identity or rejection failed");
    $display("HANDLE_COLLECTION_CONSTRUCTOR_SV_PASS");
    `SVX_GET_OBJECT(Owner, "handle_collection.instance", handle)
    if (handle.queue_handles.size() != 3 || handle.queue_handles[0] == null ||
        handle.queue_handles[1] != null || handle.queue_handles[2] != handle.queue_handles[0] ||
        handle.nested_handles["first"][0] != handle.queue_handles[0] ||
        handle.nested_handles["empty"].size() != 0 ||
        handle.vif_handles[0] != first_bus || handle.vif_handles[1] != null ||
        handle.vif_handles[2] != second_bus)
      $fatal(1, "root handle field identity failed");
    $display("HANDLE_COLLECTION_FIELD_SV_PASS");
    original = new(91);
    values = '{original, null, original};
    queue_result = handle.queue_echo(values);
    if (queue_result.size() != 3 || queue_result[0] != original || queue_result[1] != null || queue_result[2] != original)
      $fatal(1, "queue handle identity was not preserved");
    dynamic_values = new[3];
    foreach (dynamic_values[i]) dynamic_values[i] = values[i];
    dynamic_result = handle.dynamic_echo(dynamic_values);
    if (dynamic_result.size() != 3 || dynamic_result[0] != original || dynamic_result[1] != null)
      $fatal(1, "dynamic handle identity was not preserved");
    fixed_values = '{original, null};
    fixed_result = handle.fixed_echo(fixed_values);
    if (fixed_result[0] != original || fixed_result[1] != null) $fatal(1, "fixed handle identity failed");
    associative_values["first"] = original;
    associative_values["null"] = null;
    associative_result = handle.associative_echo(associative_values);
    if (associative_result.num() != 2 || associative_result["first"] != original || associative_result["null"] != null)
      $fatal(1, "associative handle identity failed");
    nested_values["first"] = values;
    nested_values["empty"] = '{};
    nested_result = handle.nested_echo(nested_values);
    if (nested_result.num() != 2 || nested_result["first"][0] != original || nested_result["first"][1] != null || nested_result["empty"].size() != 0)
      $fatal(1, "nested handle identity failed");
    queue_result = handle.transform(values, observed, changed);
    if (observed[0] != original || changed[2] != original || queue_result[1] != null)
      $fatal(1, "output or inout handle identity failed");
    $display("HANDLE_COLLECTION_SV_PASS");
    vif_values = '{first_bus, null, second_bus, first_bus};
    handle.vif_queue_echo(vif_values, vif_result);
    if (vif_result.size() != 4 || vif_result[0] != first_bus || vif_result[1] != null ||
        vif_result[2] != second_bus || vif_result[3] != first_bus) $fatal(1, "VIF queue identity failed");
    vif_dynamic_values = new[4];
    foreach (vif_dynamic_values[i]) vif_dynamic_values[i] = vif_values[i];
    handle.vif_dynamic_echo(vif_dynamic_values, vif_dynamic_result);
    if (vif_dynamic_result.size() != 4 || vif_dynamic_result[0] != first_bus || vif_dynamic_result[2] != second_bus)
      $fatal(1, "VIF dynamic identity failed");
    vif_fixed_values = '{first_bus, null};
    handle.vif_fixed_echo(vif_fixed_values, vif_fixed_result);
    if (vif_fixed_result[0] != first_bus || vif_fixed_result[1] != null) $fatal(1, "VIF fixed identity failed");
    vif_associative_values["first"] = first_bus;
    vif_associative_values["null"] = null;
    handle.vif_associative_echo(vif_associative_values, vif_associative_result);
    if (vif_associative_result.num() != 2 || vif_associative_result["first"] != first_bus ||
        vif_associative_result["null"] != null) $fatal(1, "VIF associative identity failed");
    vif_nested_values["first"] = vif_values;
    vif_nested_values["empty"] = '{};
    handle.vif_nested_echo(vif_nested_values, vif_nested_result);
    if (vif_nested_result.num() != 2 || vif_nested_result["first"][0] != first_bus ||
        vif_nested_result["first"][2] != second_bus || vif_nested_result["empty"].size() != 0)
      $fatal(1, "VIF nested identity failed");
    handle.vif_transform(vif_values, vif_observed, vif_changed);
    if (vif_observed[2] != second_bus || vif_changed[1] != null)
      $fatal(1, "VIF output/inout identity failed");
    $display("VIF_COLLECTION_SV_PASS");
    svx_start("handle_collection.close");
    svx_shutdown();
    $finish;
  end
endmodule
