// SPDX-License-Identifier: Apache-2.0
typedef enum bit[2:0] {IDLE=0, ACTIVE=5} UnitMode;
typedef struct packed {UnitMode mode;logic[3:0] flags;} UnitPacket;
typedef UnitMode UnitModes[];

class Outer;
  function new();
    $fatal(1, "Creating Inner must not allocate Outer");
  endfunction
  class Inner;
    typedef bit[7:0] UnitMode;
    typedef enum bit[1:0] {QUIET=0, READY=2} State;
    typedef struct packed {State state;logic[3:0] flags;} Packet;
    typedef State States[];
    int count;
    UnitPacket packet;
    Packet local_packet;
    function new(int seed);
      count = seed;
    endfunction
    virtual function int status();
      return count + 1;
    endfunction
    task advance(input int value, output int previous, inout int total);
      #2ns;
      previous = count;
      total += value;
      count = value;
    endtask
    static function int twice(int value);
      return value * 2;
    endfunction
    function $unit::UnitMode echo_mode(input $unit::UnitMode mode);
      return mode;
    endfunction
    function UnitPacket echo_packet(input UnitPacket value);
      return value;
    endfunction
    function UnitModes echo_modes(input UnitModes value);
      return value;
    endfunction
    function State echo_state(input State value);
      return value;
    endfunction
    function Packet echo_local_packet(input Packet value);
      return value;
    endfunction
    function States echo_states(input States value);
      return value;
    endfunction
  endclass
  typedef Inner Alias;
endclass

class OtherOuter;
  class Inner extends Outer::Inner;
    typedef enum bit[1:0] {QUIET=1, READY=3} State;
    function new(int seed);
      super.new(seed + 1);
    endfunction
    function int status();
      return super.status() + 10;
    endfunction
    function State echo_local_state(input State value);
      return value;
    endfunction
  endclass
endclass

class Outer_Inner;
  int count;
  function new(int seed);
    count = seed + 20;
  endfunction
endclass

class outer;
  class Inner;
    int count;
    function new(int seed);
      count = seed + 30;
    endfunction
  endclass
endclass
