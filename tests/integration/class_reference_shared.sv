// SPDX-License-Identifier: Apache-2.0
package class_reference_shared_pkg;
  class Item;
    int code=7;
  endclass
  class First extends svx_pkg::svx_class_reference#(Item, "sv://class_reference_shared_pkg/Item");
  endclass
  class Second extends svx_pkg::svx_class_reference#(Item, "sv://class_reference_shared_pkg/Item");
  endclass
endpackage

module class_reference_shared_tb;
  import class_reference_shared_pkg::*;
  initial begin
    Item item=new();
    Item restored;
    svtypes_pkg::remote_ref first, second, empty;
    string error;
    first=First::encode(item);
    second=Second::encode(item);
    if (first.object_number != second.object_number) $fatal(1, "duplicate object identity");
    if (!Second::decode(first, restored, error) || restored != item) $fatal(1, "decode identity mismatch");
    restored.code=19;
    if (item.code != 19) $fatal(1, "handle was cloned");
    empty=First::encode(null);
    if (!Second::decode(empty, restored, error) || restored != null) $fatal(1, "null mismatch");
    svx_pkg::svx_external_handle_registry::clear();
    if (Second::decode(first, restored, error)) $fatal(1, "stale reference accepted");
    $display("CLASS_REFERENCE_SHARED_PASS");
    $finish;
  end
endmodule
