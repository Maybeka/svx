// SPDX-License-Identifier: Apache-2.0
package struct_kinds_pkg;
  typedef struct packed { bit [7:0] tag; logic [3:0] flags; } Header;
  typedef struct {
    Header header;
    string label;
    real gain;
    int samples[2];
    byte payload[$];
  } Data;
  class Item;
    int code=7;
    function new(); endfunction
  endclass
  typedef struct {
    Item item;
    Item same_item;
    Item fixed_items[2];
    Item dynamic_items[];
    Item queue_items[$];
    Item by_key[string];
  } Handles;
  class Driver;
    Data data;
    Handles handles;
    function new();
      data.header = '{tag:8'h12, flags:4'b10xz};
      data.label = "initial";
      data.gain = 1.5;
      data.samples = '{3, 7};
      data.payload = '{1, 2};
      handles.item=new();
      handles.same_item=handles.item;
      handles.fixed_items='{handles.item, null};
      handles.dynamic_items=new[1];
      handles.dynamic_items[0]=handles.item;
      handles.queue_items='{handles.item, null};
      handles.by_key["shared"]=handles.item;
    endfunction
    function Data read(); return data; endfunction
    function Data echo(input Data value); return value; endfunction
    virtual function Data transform(input Data value); return value; endfunction
    function Data invoke_transform(input Data value); return transform(value); endfunction
    function Handles echo_handles(input Handles value); return value; endfunction
    function Handles read_handles(); return handles; endfunction
    function bit handles_match(input Handles value);
      return value.item == handles.item && value.same_item == handles.item &&
             value.fixed_items[0] == handles.item && value.fixed_items[1] == null &&
             value.dynamic_items.size() == 1 && value.dynamic_items[0] == handles.item &&
             value.queue_items.size() == 2 && value.queue_items[0] == handles.item &&
             value.queue_items[1] == null && value.by_key["shared"] == handles.item;
    endfunction
    virtual task exchange(input Data value, output Data previous, inout Data current);
      #1ns;
      previous = current;
      current = value;
      data = value;
    endtask
    task invoke_exchange(input Data value, output Data previous, inout Data current);
      exchange(value, previous, current);
    endtask
  endclass
endpackage
