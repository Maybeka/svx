package field_owner_pkg;
`ifdef SVX_DEEP_FIELD_AUDIT
  `include ".tmp/sv_field_mirror/record.sv"
`endif
  class Base;
    typedef int int_queue_t[$];
    protected int_queue_t nested_values[$] = '{'{1, 2}, '{3, 4}};
    typedef int int_dynamic_t[];
    protected int_dynamic_t nested_dynamic[];
    protected int_queue_t keyed_values[string];
`ifdef SVX_DEEP_FIELD_AUDIT
    protected DeepFieldRecord record;
    protected int fixed_matrix[2][2] = '{'{11, 12}, '{13, 14}};
`endif
    protected int count = 11;
    protected int bytes = 5;
    protected int field_offset = 6;
    protected int field_value = 7;
    protected int error = 8;
    protected int ok = 9;
    protected int response = 10;
    protected int operation[$] = '{2, 3};
    protected int fixed_values[3] = '{12, 13, 14};
    protected logic [3:0] flags = 4'bxz10;
    function new();
`ifdef SVX_DEEP_FIELD_AUDIT
      record = new();
      record.rows["left"] = '{41, 42};
      record.rows["right"] = '{43, 44};
`endif
      nested_dynamic = new[2];
      nested_dynamic[0] = new[2];
      nested_dynamic[1] = new[2];
      nested_dynamic[0] = '{1, 2};
      nested_dynamic[1] = '{3, 4};
      keyed_values["left"] = '{5, 6};
      keyed_values["right"] = '{7, 8};
    endfunction
    function logic [3:0] get_flags();
      return flags;
    endfunction
    function void set_flags(logic [3:0] value);
      flags = value;
    endfunction
    protected function int get_count();
      return count;
    endfunction
    function void set_count(int value);
      count = value;
    endfunction
  endclass
endpackage
