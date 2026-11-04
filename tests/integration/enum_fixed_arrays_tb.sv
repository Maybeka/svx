module enum_fixed_arrays_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.enum_fixed_arrays_entry");
    svx_start("enum_fixed_arrays.run");
    svx_shutdown();
    $display("ENUM_FIXED_ARRAYS_NATIVE_PASS");
    $finish;
  end
endmodule
