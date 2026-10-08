package inheritance_disable_pkg;
  class Worker;
    task wait_value(inout int changed, output int observed);
      #100ns;
      changed += 5;
      observed = changed + 1;
    endtask
    static task wait_static(inout int changed, output int observed);
      #100ns;
      changed += 5;
      observed = changed + 1;
    endtask
    virtual task hook(inout int changed, output int observed);
      wait_value(changed, observed);
    endtask
    task wait_through_python(inout int changed, output int observed);
      hook(changed, observed);
    endtask
  endclass
endpackage

`include "sv/svx_pkg.sv"
`include ".tmp/inheritance_disable/mirrors.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_load("tests.integration.inheritance_disable_test");
    fork
      begin : disabled_call
        if ($test$plusargs("FINALLY_ERROR")) svx_start("inheritance_disable.finally_error");
        else if ($test$plusargs("CALLBACK")) svx_start("inheritance_disable.callback");
        else if ($test$plusargs("STATIC")) svx_start("inheritance_disable.static");
        else svx_start("inheritance_disable.object");
        $fatal(1, "disabled inheritance call returned normally");
      end
      begin
        #10ns;
        disable disabled_call;
      end
    join
    svx_start("inheritance_disable.check");
    if ($test$plusargs("FINALLY_ERROR")) $fatal(1, "swallowed disabled inheritance finally exception");
    svx_shutdown();
    $display("SVX_INHERITANCE_DISABLE_CLEANUP_PASS");
    $finish;
  end
endmodule
