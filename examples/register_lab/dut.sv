module register_bank(
  input bit clk,
  input bit reset_n,
  input bit valid,
  input bit write,
  input bit [7:0] address,
  input bit [31:0] wdata,
  output logic [31:0] rdata
);
  logic [31:0] registers[4];
  reg [31:0] debug_cookie = 0;

  assign rdata = registers[address[3:2]];

  always @(posedge clk) begin
    if (!reset_n) begin
      foreach (registers[index]) registers[index] <= 0;
    end else if (valid && write) begin
      registers[address[3:2]] <= wdata;
    end
  end
endmodule
