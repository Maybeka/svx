`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "examples/opentitan_uart/uart_bridge.sv"
`include "mirrors.sv"

package uart_svx_test_pkg;
  import uvm_pkg::*;
  import uart_agent_pkg::*;
  import uart_env_pkg::*;
  import uart_test_pkg::*;
  import uart_svx_bridge_pkg::*;
  import svx_pkg::*;
  `include "uvm_macros.svh"

  class UartMigrationTest extends uart_base_test;
    `uvm_component_utils(UartMigrationTest)
    UartCapture tx_capture, rx_capture;
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    virtual function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      // Keep generic protocol/security checks; the plusarg selects UART model ownership.
      tx_capture = new("tx_capture", this);
      rx_capture = new("rx_capture", this);
      tx_capture.tx = 1;
      tx_capture.cfg = cfg.m_uart_agent_cfg;
      rx_capture.cfg = cfg.m_uart_agent_cfg;
    endfunction
    virtual function void connect_phase(uvm_phase phase);
      super.connect_phase(phase);
      env.m_uart_agent.monitor.tx_analysis_port.connect(tx_capture.analysis_export);
      env.m_uart_agent.monitor.rx_analysis_port.connect(rx_capture.analysis_export);
    endfunction
    virtual task run_seq(string test_seq_s, uvm_phase phase);
      UartSequence sequence_handle;
      phase.raise_objection(this);
      svx_init();
      svx_load("uart_migration");
      svx_start("uart_migration.create");
      `SVX_GET_OBJECT(uart_svx_bridge_pkg::UartSequence, "uart_migration.sequence", sequence_handle)
      configure_sequence(sequence_handle);
      if (!sequence_handle.randomize()) `uvm_fatal("UART_RANDOMIZE", "native constraints failed")
      sequence_handle.start(env.virtual_sequencer);
      svx_start("uart_migration.check");
      svx_shutdown();
      phase.drop_objection(this);
    endtask
  endclass
endpackage

module uart_svx_migration_registration;
  uvm_pkg::uvm_object_wrapper wrapper = uart_svx_test_pkg::UartMigrationTest::get_type();
endmodule
