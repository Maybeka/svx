// SPDX-License-Identifier: Apache-2.0
typedef enum bit [3:0] {IDLE = 0, ACTIVE = 5} Mode;
typedef struct packed {
  Mode mode;
  logic [3:0] flags;
} Packet;
typedef Packet PacketAlias;
typedef bit [12:0] Word;
typedef Mode Modes[];

localparam Mode START = ACTIVE;
localparam Packet INITIAL = {ACTIVE, 4'b10xz};
localparam int DEPTH = 9;

class Holder;
  typedef enum bit [1:0] {OFF = 0, ON = 1} State;
  typedef struct packed {
    State state;
    bit [7:0] data;
  } Payload;
endclass
