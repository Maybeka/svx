interface register_if(input bit clk);
  bit valid;
  bit write;
  bit [7:0] address;
  bit [31:0] wdata;
  logic [31:0] rdata;
  int tag;

  function automatic logic [31:0] read_data();
    return rdata;
  endfunction

  modport diagnostics(input address, rdata, import read_data);
endinterface
