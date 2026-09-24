package field_pkg;
  virtual class Base;
    function new();
    endfunction
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/field_projection_inheritance/mirrors.sv"

package field_user_pkg;
  import svx_projection_tests_integration_field_projection_inheritance_test_PythonLayerProxy_pkg::*;

  class Final extends PythonLayerProxy;
    function new();
      super.new();
    endfunction
  endclass
endpackage

module tb;
  import field_user_pkg::*;
  import svx_pkg::*;

  initial begin
    Final value;
    svx_init();
    svx_load("tests.integration.field_projection_inheritance_test");
    value = new();
    if (value.retry != 7) begin
      $fatal(2, "Python projected field write did not update the SV BProxy field");
    end
    if (value.history.size() != 2 || value.history[0] != 4 || value.history[1] != 9) begin
      $fatal(2, "Python queue path operations did not update the SV BProxy field");
    end
    if (!value.mapping.exists(2) || value.mapping[2] != 8 || value.mapping.exists(1)) begin
      $fatal(2, "Python associative path operations did not update the SV BProxy field");
    end
    svx_release_object(value.__svx_remote_object_id);
    svx_start("field_projection.check_release");
    $display("FIELD_PROJECTION_INHERITANCE_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
