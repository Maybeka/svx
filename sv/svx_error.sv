`ifndef SVX_ERROR__SV
`define SVX_ERROR__SV

task automatic svx_fatal_svx(string source, string message);
  $fatal(2, "SVX FATAL [%s]: %s", source, message);
endtask

export "DPI-C" task svx_fatal_svx;

`endif
