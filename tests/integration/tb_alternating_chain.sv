package chain_pkg;
  virtual class A;
    int count = 11;
    function new();
    endfunction

    virtual task base_check();
      count += 10;
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

    static function int scale(input int delta);
      return delta * 5;
    endfunction

    function new(input longint unsigned object_id = 0);
      super.new(object_id);
    endfunction

    task c_check();
      if (count != 31) $fatal(2, "C cannot see Python write to inherited A.count");
      count = 37;
      b_check();
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
    time before_static_wait;
    svx_init();
    svx_mirror_sv_chain_user_pkg_C::register_C_factory();
    svx_load("tests.integration.alternating_chain_test");
`ifdef SVX_ALTERNATING_STATIC
    if (svx_proxy_alternating_chain_test::B::scale(7) != 21)
      $fatal(2, "qualified Python B static dispatch mismatch");
    if (C::scale(7) != 35) $fatal(2, "qualified SV C static dispatch mismatch");
    before_static_wait = $time;
    svx_proxy_alternating_chain_test::B::wait_once();
    C::wait_once();
    if ($time - before_static_wait != 4ns) $fatal(2, "inherited static task timing mismatch");
    $display("ALTERNATING_STATIC_NO_INSTANCE_PASS");
`endif
    svx_start("alternating_chain.run");
    if (C::c_check_count != 1) begin
      $fatal(2, "Python D call did not reach the C portion");
    end
    direct_c = new();
    direct_c.base_check();
    direct_c.b_check();
    if (direct_c.count != 22) $fatal(2, "B callback or explicit A base call did not update SV-created C's inherited field");
    svx_start("alternating_chain.verify_direct_c");
    $display("ALTERNATING_CHAIN_PASS");
    svx_shutdown();
    $finish;
  end
endmodule
