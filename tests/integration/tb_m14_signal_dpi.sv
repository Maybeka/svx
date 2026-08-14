module tb;
  import "DPI-C" context function int svx_vpi_signal_self_test(int phase,
    string flag_path, string data_path
  );
  import "DPI-C" context function int svx_vpi_signal_four_state_self_test(
    int phase, string path
  );

  logic flag;
  logic [7:0] data;
  logic [7:0] logic_data;
  assign flag = 0;
  assign data = 0;

  initial begin
    int result;
    logic_data = 8'b10xz01z0;
    #1;
    if (!$test$plusargs("FOUR_STATE_ONLY")) begin
      for (int phase = 0; phase < 4; phase++) begin
        result = svx_vpi_signal_self_test(phase, "tb.flag", "tb.data");
        if (result != 1) begin
          $fatal(1, "direct SV-to-DPI VPI signal service failed at stage %0d", result);
        end
        #1;
      end
    end
    if (!$test$plusargs("TWO_STATE_ONLY")) begin
      result = svx_vpi_signal_four_state_self_test(0, "tb.logic_data");
      if (result != 1) begin
        $fatal(1, "direct four-state VPI read/write failed at stage %0d", result);
      end
      #1;
      result = svx_vpi_signal_four_state_self_test(1, "tb.logic_data");
      if (result != 1 || logic_data !== 8'bzx10xz01) begin
        $fatal(1, "direct four-state VPI verification failed at stage %0d", result);
      end
    end
    if (!$test$plusargs("FOUR_STATE_ONLY") &&
        (flag !== 1 || data !== 8'ha5)) begin
      $fatal(1, "unexpected final values: flag=%b data=%h", flag, data);
    end
    $display("M14_SIGNAL_DIRECT_DPI_PASS");
    $finish;
  end
endmodule
