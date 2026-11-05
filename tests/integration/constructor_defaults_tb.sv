module constructor_defaults_tb;
  import svx_pkg::*;
  initial begin
    svx_mirror_sv_constructor_defaults_pkg_Driver::Driver implicit_args, explicit_args;
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.constructor_defaults_entry");
    implicit_args = new();
    explicit_args = new(13, "sv-driver");
    assert (implicit_args.seed == 7 && implicit_args.label == "default-driver") else $fatal(1, "constructor defaults changed");
    assert (explicit_args.seed == 13 && explicit_args.label == "sv-driver") else $fatal(1, "constructor arguments changed");
    svx_start("constructor_defaults.run");
    svx_shutdown();
    $display("CONSTRUCTOR_DEFAULTS_NATIVE_PASS");
    $finish;
  end
endmodule
