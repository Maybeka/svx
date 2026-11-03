// SPDX-License-Identifier: Apache-2.0
package nested_struct_ref_pkg;
  class Item;
    int code = 42;
  endclass
  typedef Item item_queue_t[$];
  typedef struct { item_queue_t queues[$]; } Payload;
  class Driver;
    Payload payload;
    function new();
      Item item = new;
      item_queue_t queue;
      queue.push_back(item);
      payload.queues.push_back(queue);
    endfunction
    function Payload read(); return payload; endfunction
    function bit valid(input Payload value);
      return value.queues.size() == 1 && value.queues[0].size() == 1 &&
             value.queues[0][0].code == 42;
    endfunction
  endclass
endpackage
