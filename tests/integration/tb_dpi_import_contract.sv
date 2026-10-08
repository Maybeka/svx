`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"

module tb;
  import svx_pkg::*;
  initial begin
    svx_init();
    if (svx_runtime_abi_version() != SVX_SV_RUNTIME_ABI_VERSION)
      $fatal(2, "DPI runtime version return value disagrees with the SV contract");
    if (svx_runtime_state_name() == "")
      $fatal(2, "DPI string return was empty after initialization");
    svx_shutdown();
    $display("SVX_DPI_IMPORT_CONTRACT_PASS");
    $finish;
  end
endmodule
