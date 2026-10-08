`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/channel_type_matrix/types.sv"

module tb;
  import svx_pkg::*;

  task automatic echo_values();
    MatrixValue value;
    for (int i = 0; i < 3; i++) begin
      svx_get_MatrixValue("matrix.req", value);
      if (value.packed_value != 13'h1234 || value.four_state !== 9'bz0x010101)
        $fatal(1, "packed/four-state channel value mismatch");
      if (value.mode != MATRIX_SECOND || value.real_value != 1.25)
        $fatal(1, "enum/real channel value mismatch");
      if (value.fixed[1] != -2 || value.dynamic.size() != 2 ||
          value.dynamic[0] != i || value.queue_value[1] != 9 ||
          value.nested[0][1] != 2 || value.lookup["alpha"] != 17)
        $fatal(1, "collection channel value mismatch");
      if (i == 0) begin
        if (value.first != null || value.shared_node != null)
          $fatal(1, "null graph value mismatch");
      end else if (value.first == null || value.first != value.shared_node ||
                   value.first.link != value.first || value.first.number != i)
        $fatal(1, "graph identity/cycle mismatch");
      if (value.reference != null && !value.reference.is_null())
        $fatal(1, "null RemoteRef mismatch");
      svx_put_MatrixValue("matrix.rsp", value);
    end
  endtask

  initial begin
    svx_init();
    svx_load("tests.integration.channel_type_matrix");
    fork
      svx_start("channel_matrix.run");
      echo_values();
    join
    svx_shutdown();
    $finish;
  end
endmodule
