module nested_associative_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.nested_associative_entry");
    svx_start("nested_associative.run");
    svx_shutdown();
    $display("NESTED_ASSOCIATIVE_NATIVE_PASS");
    $finish;
  end
endmodule
