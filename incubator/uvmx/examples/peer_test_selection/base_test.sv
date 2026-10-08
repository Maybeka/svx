package uvmx_peer_pkg;
  import uvm_pkg::*;
  import svx_pkg::*;
  import uvmx_types_pkg::*;
  `include "uvm_macros.svh"

  class uvmx_python_base extends uvm_test;
    `uvm_component_utils(uvmx_python_base)

    function new(string name = "", uvm_component parent = null);
      super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
      super.run_phase(phase);
      fork
        begin
          BootstrapTransaction transaction;
          svx_get_BootstrapTransaction("uvmx.peer.transaction", transaction);
          if (transaction.address != 16'h0041 || transaction.data != 73) begin
            $fatal(2, "UVMX typed monitor received unexpected transaction");
          end
          `uvm_info("UVMX/MONITOR", "received typed Python transaction", UVM_LOW)
        end
      join_none
    endtask
  endclass

  class legacy_sv_test extends uvm_test;
    `uvm_component_utils(legacy_sv_test)

    function new(string name = "", uvm_component parent = null);
      super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
      phase.raise_objection(this, "legacy SV test active");
      #1ns;
      `uvm_info("UVMX/LEGACY", "legacy SV test selected", UVM_LOW)
      phase.drop_objection(this, "legacy SV test complete");
    endtask
  endclass
endpackage : uvmx_peer_pkg
