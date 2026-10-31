// SPDX-License-Identifier: Apache-2.0
package scoped_base_pkg;
  class Base;
    int count;
    function new(int seed);count=seed;endfunction
    virtual function int status();return count;endfunction
  endclass
endpackage

package scoped_classes_pkg;
  typedef enum bit[3:0] {IDLE=0, ACTIVE=5} Mode;
  typedef struct packed {bit[7:0] tag; logic[3:0] flags; Mode mode;} Packet;
  class Outer;
    typedef enum bit[3:0] {LOCAL_IDLE=0, LOCAL_ACTIVE=7} LocalMode;
    typedef struct packed {LocalMode mode; logic[3:0] flags;} LocalPacket;
    class Inner extends scoped_base_pkg::Base;
      Packet packet;
      LocalPacket local_packet;
      function new(int seed);super.new(seed+1);packet='0;endfunction
      function int status();return super.status()+10;endfunction
      task advance(input int value, output int previous);
        #2ns; previous=count;count=value;
      endtask
      static function int twice(int value);return value*2;endfunction
      function Packet echo(Packet value);return value;endfunction
      function LocalPacket echo_local(LocalPacket value);return value;endfunction
    endclass
    typedef Inner Alias;
  endclass
  class OtherOuter;
    class Inner extends scoped_base_pkg::Base;
      function new(int seed);super.new(seed+2);endfunction
      function int status();return super.status()+20;endfunction
    endclass
  endclass
  class outer;
    class Inner extends scoped_base_pkg::Base;
      function new(int seed);super.new(seed+4);endfunction
      function int status();return super.status()+40;endfunction
    endclass
  endclass
  class Outer_Inner extends scoped_base_pkg::Base;
    function new(int seed);super.new(seed+3);endfunction
    function int status();return super.status()+30;endfunction
  endclass
endpackage
