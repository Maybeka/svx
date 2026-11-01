// SPDX-License-Identifier: Apache-2.0
package scoped_nominal_bus_types_pkg;
  typedef enum bit[1:0] {IDLE, ACTIVE} Mode;
  typedef struct packed {Mode mode; logic[12:0] data;} Payload;
  typedef Mode Modes[$];
  typedef Payload Packets[2];
  typedef Payload Samples[];
  typedef Payload PacketMap[string];
endpackage

interface scoped_bus_if;
  import scoped_nominal_bus_types_pkg::*;
  logic ready = 1;
  logic [7:0] data = 0;
  Mode mode = IDLE;
  Payload payload = '{IDLE, 13'h123};
  Modes modes;
  task automatic write(input logic[7:0] value);
    #1ns; data = value;
  endtask
  function automatic logic[7:0] read(); return data; endfunction
  function automatic Mode echo_mode(input Mode value, output Mode previous, inout Mode changed);
    previous = mode; mode = value; changed = value; return mode;
  endfunction
  function automatic Payload echo_payload(input Payload value); return value; endfunction
  function automatic Modes echo_modes(input Modes values); return values; endfunction
  function automatic Packets echo_packets(input Packets values); return values; endfunction
  function automatic Samples echo_samples(input Samples values); return values; endfunction
  function automatic PacketMap echo_map(input PacketMap values); return values; endfunction
  function automatic void exchange_nominal_collections(input Modes incoming, output Modes previous, inout Samples changed);
    previous = modes; modes = incoming;
    foreach (changed[index]) changed[index].mode = ACTIVE;
  endfunction
  task automatic exchange_nominal(input Payload incoming, output Payload previous, inout Payload changed);
    #2ns; previous = payload; payload = incoming; changed.mode = incoming.mode;
  endtask
  modport master(input ready, output data, inout mode, payload,
    import write, read, echo_mode, echo_payload, echo_modes, echo_packets,
           echo_samples, echo_map, exchange_nominal, exchange_nominal_collections);
endinterface
