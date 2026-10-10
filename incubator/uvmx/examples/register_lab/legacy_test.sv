package register_lab_uvm_pkg;
  import uvm_pkg::*;
  import svx_pkg::*;
  `include "uvm_macros.svh"

  class register_lab_sv_test extends uvm_test;
    `uvm_component_utils(register_lab_sv_test)

    function new(string name = "", uvm_component parent = null);
      super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
      phase.raise_objection(this);
      svx_run_test("examples.register_lab.scenarios", "smoke");
      $display("REGISTER_LAB_UVM_PASS");
      phase.drop_objection(this);
    endtask
  endclass
endpackage
