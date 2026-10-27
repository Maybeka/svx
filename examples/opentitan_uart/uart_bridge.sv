// SPDX-License-Identifier: Apache-2.0
// Compile after the unmodified upstream UART environment and before SVX mirrors.
package uart_svx_bridge_pkg;
  import uvm_pkg::*;
  import uart_agent_pkg::*;
  import uart_env_pkg::*;
  `include "uvm_macros.svh"

  class UartSequence extends uart_smoke_vseq;
    static uart_item tx_items[$], rx_items[$];
    static bit tx_parity_enabled[$], tx_odd_parity[$];
    static bit rx_parity_enabled[$], rx_odd_parity[$];
    function new();
      super.new("svx_uart_sequence");
      do_interrupt = 0;
    endfunction

    // The upstream helpers first consult ctrl.get_mirrored_value(), which is
    // maintained by the scoreboard. Poll actual CSR responses when it is off.
    virtual task spinwait_txidle();
      csr_utils_pkg::csr_spinwait(.ptr(ral.status.txidle), .exp_data(1),
          .spinwait_delay_ns(100), .timeout_ns(uart_reg_pkg::TxFifoDepth * 1_250_000));
    endtask
    virtual task spinwait_rxidle();
      csr_utils_pkg::csr_spinwait(.ptr(ral.status.rxidle), .exp_data(1),
          .spinwait_delay_ns(100), .timeout_ns(uart_reg_pkg::RxFifoDepth * 1_250_000));
    endtask

    virtual task read_rx(output int value);
      bit [31:0] raw;
      csr_utils_pkg::csr_rd(.ptr(ral.rdata), .value(raw));
      value = raw;
    endtask

    function int observed_count(bit tx);
      return tx ? tx_items.size() : rx_items.size();
    endfunction
    function uart_item observed_item(bit tx, int index);
      if (index < 0 || index >= observed_count(tx))
        `uvm_fatal("UART_OBSERVATION_INDEX", "observation index out of range")
      return tx ? tx_items[index] : rx_items[index];
    endfunction
    function bit parity_enabled(bit tx, int index);
      return tx ? tx_parity_enabled[index] : rx_parity_enabled[index];
    endfunction
    function bit parity_odd(bit tx, int index);
      return tx ? tx_odd_parity[index] : rx_odd_parity[index];
    endfunction
    function int item_data(uart_item item);
      return item.data;
    endfunction
    function int item_frame(uart_item item);
      return {item.parity, item.stop_bit, item.start_bit};
    endfunction
    function int item_identity(uart_item item);
      return item.get_inst_id();
    endfunction
    function bit same_item(uart_item first, uart_item second);
      return first == second;
    endfunction
    function uart_item make_item(int data);
      uart_item item = new("python_created_item");
      item.data = data;
      return item;
    endfunction
    function void set_item_data(uart_item item, int data);
      item.data = data;
    endfunction
  endclass

  class UartCapture extends uvm_subscriber #(uart_item);
    bit tx;
    int captured;
    uart_agent_cfg cfg;
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    virtual function void write(uart_item t);
      uart_item snapshot;
      if (!$cast(snapshot, t.clone()))
        `uvm_fatal("UART_SNAPSHOT", "cannot clone native uart_item")
      // The producer may reuse its item. Retain an owned native snapshot.
      if (tx) begin
        captured++;
        if ($test$plusargs("UART_SVX_DROP_TX") && captured == 1) return;
        if ($test$plusargs("UART_SVX_CORRUPT_TX")) snapshot.data ^= 8'h01;
        if ($test$plusargs("UART_SVX_REORDER_TX") && captured == 2)
          UartSequence::tx_items.push_front(snapshot);
        else UartSequence::tx_items.push_back(snapshot);
        UartSequence::tx_parity_enabled.push_back(cfg.en_parity);
        UartSequence::tx_odd_parity.push_back(cfg.odd_parity);
      end else begin
        UartSequence::rx_items.push_back(snapshot);
        UartSequence::rx_parity_enabled.push_back(cfg.en_parity);
        UartSequence::rx_odd_parity.push_back(cfg.odd_parity);
      end
    endfunction
  endclass
endpackage
