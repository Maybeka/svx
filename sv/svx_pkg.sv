`ifndef SVX_PKG__SV
`define SVX_PKG__SV

package svx_pkg;
  timeunit 1ns;
  timeprecision 1ps;

  `include "sv/svx_defs.svh"
  `include "sv/svx_init.sv"
  `include "sv/svx_timing.sv"
  `include "sv/svx_process.sv"
  `include "sv/svx_fork.sv"
  `include "sv/svx_channel.sv"
`ifdef SVX_ENABLE_VPI_SIGNAL
  `include "sv/svx_signal.sv"
`endif
  `include "sv/svx_inheritance.sv"
  `include "sv/svx_error.sv"
endpackage

`endif
