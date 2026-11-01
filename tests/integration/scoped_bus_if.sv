interface scoped_bus_if;
  logic ready = 1;
  logic [7:0] data = 0;
  task automatic write(input logic [7:0] value);
    #1ns;
    data = value;
  endtask
  function automatic logic [7:0] read();
    return data;
  endfunction
  modport master(input ready, output data, import write, read);
endinterface
