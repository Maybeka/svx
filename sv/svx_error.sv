`ifndef SVX_ERROR__SV
`define SVX_ERROR__SV

function automatic void svx_fatal_svx(string source, string message);
  $fatal(2, "SVX FATAL [%s]: %s", source, message);
endfunction

export "DPI-C" function svx_fatal_svx;

`endif
