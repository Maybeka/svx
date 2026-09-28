package chain_pkg;
  virtual class A;
    function new();
    endfunction

    virtual task base_check();
      $fatal(2, "A.base_check must dispatch to Python B");
    endtask
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/alternating_chain/stages/common.svh"
`include ".tmp/alternating_chain/stages/after_sv_chain_pkg_A_d1633a1682.svh"
`include ".tmp/alternating_chain/stages/before_sv_chain_user_pkg_C_cb51118d6f.svh"

`SVX_PY_PROXY(B, "py://tests/integration/alternating_chain/B", A)
package chain_user_pkg;
  import chain_pkg::*;
  import svx_proxy_alternating_chain_test::*;

  class C extends B;
    static int c_check_count;

    function new(input longint unsigned object_id = 0);
      super.new(object_id);
    endfunction

    task c_check();
      c_check_count++;
    endtask

    task trigger_base_check();
      base_check();
    endtask
  endclass
endpackage

`include ".tmp/alternating_chain/stages/after_sv_chain_user_pkg_C_cb51118d6f.svh"

module tb;
  import chain_user_pkg::*;
  import svx_pkg::*;

  initial begin
    C direct_c;
    svx_init();
    svx_mirror_sv_chain_user_pkg_C::register_C_factory();
    svx_load("tests.integration.alternating_chain_test");
    svx_start("alternating_chain.run");
    if (C::c_check_count != 1) begin
      $fatal(2, "Python D call did not reach the C portion");
    end
    direct_c = new();
    direct_c.base_check();
    svx_start("alternating_chain.verify_direct_c");
    $display("ALTERNATING_CHAIN_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
