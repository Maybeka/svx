`ifndef UVMX_PKG__SV
`define UVMX_PKG__SV

package uvmx_pkg;
  import uvm_pkg::*;
  import svx_pkg::*;
  `include "uvm_macros.svh"
  `include "uvmx_registration.sv"
  `include "uvmx_callbacks.sv"
  `include "uvmx_factory.sv"
  `include "uvmx_bridge.sv"
endpackage : uvmx_pkg

`endif
