interface external_bus_if;
  logic ready;
  logic [7:0] data;

  task automatic write(input logic [7:0] value);
    data = value;
  endtask

  function automatic logic [7:0] read();
    return data;
  endfunction

  modport master(input ready, output data, import write, read);
endinterface
