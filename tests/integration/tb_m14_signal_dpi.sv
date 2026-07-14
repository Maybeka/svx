module tb;
  import "DPI-C" context function int svx_vpi_signal_self_test(int phase,
    string flag_path, string data_path
  );

  logic flag;
  logic [7:0] data;
  assign flag = 0;
  assign data = 0;

  initial begin
    int result;
    #1;
    for (int phase = 0; phase < 4; phase++) begin
      result = svx_vpi_signal_self_test(phase, "tb.flag", "tb.data");
      if (result != 1) begin
        $fatal(1, "direct SV-to-DPI VPI signal service failed at stage %0d", result);
      end
      #1;
    end
    if (flag !== 1 || data !== 8'ha5) begin
      $fatal(1, "unexpected final values: flag=%b data=%h", flag, data);
    end
    $display("M14_SIGNAL_DIRECT_DPI_PASS");
    $finish;
  end
endmodule
