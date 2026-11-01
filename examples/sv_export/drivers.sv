// SPDX-License-Identifier: Apache-2.0
interface export_status_if;
  bit ready;
  modport view(input ready);
endinterface

package export_base_pkg;
  parameter int SEED=6;
  typedef enum bit [3:0] {BASE_IDLE=0, BASE_ACTIVE=7} Mode;
  class Base;
    int count;
    function new(int seed); count = seed; endfunction
    virtual function int status(); return count; endfunction
  endclass
endpackage

package export_driver_pkg;
  import export_base_pkg::*;
  typedef enum bit [3:0] {IDLE=0, ACTIVE=5} Mode;
  typedef struct packed {
    bit [7:0] tag;
    logic [3:0] flags;
    Mode mode;
    export_base_pkg::Mode base_mode;
  } Packet;
  localparam int COUNT=SEED*3;
  localparam int NEGATIVE=-4;
  localparam int ZERO=0;
  localparam string LABEL="hello";
  localparam string EMPTY="";
  localparam real GAIN=2.5;
  localparam logic [3:0] FLAGS=4'b10xz;
  localparam Packet DEFAULT_PACKET='{tag:8'h81, flags:4'bxz10,
                                      mode:ACTIVE, base_mode:BASE_ACTIVE};
  localparam int TABLE[3]='{1,-2,3};
  class Driver extends Base;
    localparam int DEFAULT_SEED=COUNT;
    localparam Mode DEFAULT_MODE=IDLE;
    Packet packet;
    function new(int seed); super.new(seed); packet='0; endfunction
    function int status(); return super.status() + 1; endfunction
    task advance(input int value, output int previous, inout int total);
      #2ns;
      previous = count;
      count = value;
      total += value;
    endtask
    static function int twice(int value); return value * 2; endfunction
    function Mode echo_mode(Mode value); return value; endfunction
    function Packet echo_packet(Packet value); return value; endfunction
    function export_base_pkg::Mode echo_base_mode(export_base_pkg::Mode value); return value; endfunction
  endclass
  class Other;
    int tag;
    function new(int value); tag=value; endfunction
  endclass
  int package_counter=0;
  function automatic void clear(); package_counter=0; endfunction
  function automatic int add(int left, int right, output int previous);
    previous=package_counter;
    package_counter++;
    return left+right+COUNT;
  endfunction
  task automatic step(input int amount, output int previous, inout int total);
    #3ns;
    previous=package_counter;
    package_counter+=amount;
    total+=package_counter;
  endtask
  function automatic Packet echo_packet(Packet value); return value; endfunction
  function automatic Other make_other(int tag);
    Other value=new(tag);
    return value;
  endfunction
  function automatic int other_tag(Other value); return value.tag; endfunction
  function automatic bit same_other(Other left, Other right); return left==right; endfunction
  virtual export_status_if.view observed_bus;
  function automatic virtual export_status_if.view get_bus(); return observed_bus; endfunction
  function automatic bit bus_ready(virtual export_status_if.view value); return value.ready; endfunction
  function automatic int invoke_sv(int value); return value+9; endfunction
endpackage
