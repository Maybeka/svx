module class_constants_tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.class_constants_entry");
    svx_start("class_constants.run");
    if (class_constants_pkg::Limits::WIDTH != 8)
      $fatal(1, "Python snapshot mutation changed a native constant");
    if (class_constants_pkg::Limits::DEFAULT_PACKET.tag != 8'h91)
      $fatal(1, "Python snapshot mutation changed a native packed constant");
    svx_shutdown();
    $display("CLASS_CONSTANTS_NATIVE_PASS");
    $finish;
  end
endmodule
