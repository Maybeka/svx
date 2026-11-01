// SPDX-License-Identifier: Apache-2.0
class SharedBase;
  typedef enum bit[8:0] {IDLE=0, ACTIVE=1} State;
  typedef struct packed {State state; logic[8:0] data;} Packet;
  local static int allocations;
  int count;
  State state;
  Packet packet;
  function new(int seed);
    allocations++;
    count = seed;
    state = ACTIVE;
    packet = '{ACTIVE, 9'h1a};
  endfunction
  virtual function int compute(int value); count += value; return count; endfunction
  function Packet current_packet(); return packet; endfunction
  static function int allocation_count(); return allocations; endfunction
  task advance(input int steps, output Packet previous, inout int total);
    #1ns; previous = packet; count += steps; total += count;
  endtask
endclass

module lexical_owner #(int W=8);
  class Driver extends SharedBase;
    typedef enum bit[W-1:0] {LOCAL_ZERO=0, LOCAL_ONE=1} LocalState;
    LocalState own_state = LOCAL_ONE;
    bit[W-1:0] local_count;
    function new(int seed); super.new(seed + 1); local_count = seed; endfunction
    virtual function int compute(int value); return super.compute(value) + int'(local_count); endfunction
  endclass
endmodule
