interface vif_handle_if;
  logic [7:0] data;

  task automatic write(input logic [7:0] value);
    data = value;
  endtask

  function automatic logic [7:0] read();
    return data;
  endfunction

  modport master(output data, import write, read);
endinterface

class VifHolder;
  virtual vif_handle_if.master vif;

  function new(virtual vif_handle_if.master vif);
    this.vif = vif;
  endfunction

  task write_through(input logic [7:0] value);
    vif.write(value);
  endtask

  function logic [7:0] read_through();
    return vif.read();
  endfunction
endclass

task automatic replace_vif(
  ref virtual vif_handle_if.master target,
  input virtual vif_handle_if.master source
);
  target = source;
endtask

module tb;
  vif_handle_if bus_a();
  vif_handle_if bus_b();

  initial begin
    virtual vif_handle_if.master first;
    virtual vif_handle_if.master second;
    VifHolder holder;

    first = bus_a;
    second = bus_b;
    holder = new(first);
    holder.write_through(8'h3c);
    if (bus_a.data != 8'h3c || holder.read_through() != 8'h3c) begin
      $fatal(2, "VIF member access did not reach the referenced interface");
    end

    replace_vif(first, second);
    holder = new(first);
    holder.write_through(8'ha5);
    if (bus_b.data != 8'ha5 || holder.read_through() != 8'ha5) begin
      $fatal(2, "VIF formal-handle passing did not preserve the referenced interface");
    end
    if (bus_a.data != 8'h3c) begin
      $fatal(2, "VIF reassignment unexpectedly changed the original interface");
    end

    $display("VIF_HANDLE_SEMANTICS_PASS");
    $finish;
  end
endmodule
