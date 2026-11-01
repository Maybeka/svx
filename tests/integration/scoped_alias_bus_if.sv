package scoped_bus_types_pkg;
  typedef logic [7:0] Byte;
  typedef Byte Bytes[$];
  typedef Byte ByteMap[string];
  typedef Byte Pair[2];
  typedef int Signed;
  typedef real Sample;
  typedef string Text;
endpackage

interface scoped_bus_if;
  import scoped_bus_types_pkg::*;
  logic ready = 1;
  Byte data = 0;
  Bytes items;
  task automatic write(input Byte value);
    #1ns;
    data = value;
  endtask
  function automatic Byte read();
    return data;
  endfunction
  function automatic Bytes append_data(input Bytes values);
    values.push_back(data);
    return values;
  endfunction
  task automatic exchange_values(input Bytes incoming, output Bytes previous, inout Bytes changed);
    #2ns;
    previous = items;
    items = incoming;
    changed.push_back(data);
  endtask
  function automatic ByteMap echo_map(input ByteMap values);
    return values;
  endfunction
  function automatic Pair echo_pair(input Pair values);
    return values;
  endfunction
  function automatic Signed offset(input Signed value);
    return value - 3;
  endfunction
  function automatic Sample measure(input Sample value);
    return value + 0.5;
  endfunction
  function automatic Text decorate(input Text value);
    return {"bus:", value};
  endfunction
  modport master(input ready, output data,
                 import write, read, append_data, exchange_values, echo_map,
                        echo_pair, offset, measure, decorate);
endinterface
