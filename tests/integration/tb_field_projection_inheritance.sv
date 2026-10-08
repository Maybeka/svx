package field_pkg;
  virtual class Base;
    int constructor_sum;
    function new(input int self, svx_self, _native, encode_constructor,
                 bind_instance, object_id, SVMirror, svx_object_id);
      constructor_sum = self + svx_self + _native + encode_constructor +
                        bind_instance + object_id + SVMirror + svx_object_id;
    endfunction
    function int collisions(input int self, svx_self, invoke_sv, svx_invoke_sv,
                            invoke_sv_static, svx_invoke_sv_static);
      return self + svx_self + invoke_sv + svx_invoke_sv + invoke_sv_static + svx_invoke_sv_static;
    endfunction
    static function int collisions_static(input int self, svx_self, invoke_sv, svx_invoke_sv,
                                          invoke_sv_static, svx_invoke_sv_static);
      return self + svx_self + invoke_sv + svx_invoke_sv + invoke_sv_static + svx_invoke_sv_static;
    endfunction
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/field_projection_inheritance/mirrors.sv"

package field_user_pkg;
  import svx_proxy_field_projection_inheritance_test::*;

  class Final extends PythonLayer;
    function new();
      super.new(1, 2, 3, 4, 5, 6, 7, 8);
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
    if (value.constructor_sum != 36) begin
      $fatal(2, "Generated constructor changed colliding parameter values");
    end
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
    svx_start("field_projection.check_failed_release");
    $display("FIELD_PROJECTION_INHERITANCE_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
