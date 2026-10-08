interface external_bus_if;
  logic ready;
  logic [7:0] data;

  task automatic write(input logic [7:0] value);
    data = value;
  endtask

  function automatic logic [7:0] read();
    return data;
  endfunction

  function automatic void snapshot;
    output logic [7:0] first, second;
    first = data;
    second = data + 1;
  endfunction

  modport master(input ready, output data, import write, read, snapshot);
endinterface
