module class_enum_arrays_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.class_enum_arrays_entry");
    svx_start("class_enum_arrays.run");
    svx_shutdown();
    $display("CLASS_ENUM_ARRAYS_NATIVE_PASS");
    $finish;
  end
endmodule
