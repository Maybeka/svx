package type_identity_pkg;
  class Driver #(CODE = 'hffff, NEGATIVE = 8'shff, MASK = 64'h8000000000000001);
    int data, data_type, data_read, data_write;
    function new(int seed = 7);
      data = seed;
      data_type = seed + 1;
      data_read = seed + 2;
      data_write = seed + 3;
    endfunction
    function bit same(input Driver#(CODE, NEGATIVE, MASK) other);
      return this == other;
    endfunction
    function Driver#(CODE, NEGATIVE, MASK) self_ref(); return this; endfunction
    function int unsigned code(); return CODE; endfunction
    function int negative(); return NEGATIVE; endfunction
    function void exchange(input int payload[$], input int payload_type,
                           inout int count, output int result);
      count += payload.size();
      result = count + payload_type;
    endfunction
  endclass
endpackage
