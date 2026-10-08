package handle_collection_pkg;
  class Item;
    int value;
    function new(int value = 0); this.value = value; endfunction
  endclass
  typedef Item queue_t[$];
  typedef Item dynamic_t[];
  typedef Item fixed_t[2];
  typedef Item associative_t[string];
  typedef queue_t nested_t[string];
  typedef queue_t matrix_t[$];
  typedef virtual handle_collection_if.master vif_t;
  typedef vif_t vif_queue_t[$];
  typedef vif_t vif_dynamic_t[];
  typedef vif_t vif_fixed_t[2];
  typedef vif_t vif_associative_t[string];
  typedef vif_queue_t vif_nested_t[string];
  class ConstructorOwner;
    local static int construction_count;
    local queue_t items;
    local nested_t groups;
    local vif_queue_t ports;
    function new(input Item items[$], input Item groups[string][$], input vif_t ports[$]);
      construction_count++;
      this.items = items;
      this.groups = groups;
      this.ports = ports;
    endfunction
    function queue_t get_items(); return items; endfunction
    static function int get_construction_count(); return construction_count; endfunction
    function nested_t get_groups(); return groups; endfunction
    function void get_ports(output vif_t result[$]); result = ports; endfunction
  endclass
  class Owner;
    queue_t queue_handles;
    dynamic_t dynamic_handles;
    matrix_t matrix_handles;
    nested_t nested_handles;
    vif_queue_t vif_handles;
    local Item original = new(42);
    function queue_t seed(); return '{original, null, original}; endfunction
    virtual function queue_t queue_echo(input Item values[$]); return values; endfunction
    virtual function dynamic_t dynamic_echo(input Item values[]); return values; endfunction
    virtual function fixed_t fixed_echo(input Item values[2]); return values; endfunction
    virtual function associative_t associative_echo(input Item values[string]); return values; endfunction
    virtual function nested_t nested_echo(input Item values[string][$]); return values; endfunction
    virtual function void vif_queue_echo(input vif_queue_t values, output vif_queue_t result); result = values; endfunction
    virtual function void vif_dynamic_echo(input vif_dynamic_t values, output vif_dynamic_t result); result = values; endfunction
    virtual function void vif_fixed_echo(input vif_fixed_t values, output vif_fixed_t result); result = values; endfunction
    virtual function void vif_associative_echo(input vif_associative_t values, output vif_associative_t result); result = values; endfunction
    virtual function void vif_nested_echo(input vif_nested_t values, output vif_nested_t result); result = values; endfunction
    virtual function void vif_transform(input vif_queue_t values, output vif_queue_t observed, inout vif_queue_t changed);
      observed = values;
      changed = values;
    endfunction
    virtual function queue_t transform(input Item values[$], output Item observed[$], inout Item changed[$]);
      observed = values;
      changed = values;
      return values;
    endfunction
  endclass
endpackage
