module migration_register_bank(
  input logic clk, reset_n, valid, write,
  input logic [7:0] address,
  input logic [31:0] wdata,
  input bit corrupt_read, unknown_read,
  output wire ready,
  output wire [31:0] rdata
);
  logic [31:0] registers[4];
  logic [1:0] waited;
  assign ready = reset_n && valid && (waited == (address[3:2] % 3));
  assign rdata = unknown_read ? 32'hx :
                 registers[address[3:2]] ^ (corrupt_read ? 32'h1 : 32'h0);

  always @(posedge clk) begin
    if (!reset_n) begin
      waited <= 0;
      foreach (registers[i]) registers[i] <= 0;
    end else begin
      if (valid && !ready) waited <= waited + 1'b1;
      else waited <= 0;
      if (valid && ready && write) registers[address[3:2]] <= wdata;
    end
  end
endmodule
