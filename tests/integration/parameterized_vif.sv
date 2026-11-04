// SPDX-License-Identifier: Apache-2.0
package parameterized_vif_types_pkg;
  typedef bit[6:0] Word;
  typedef enum bit[1:0] {IDLE=0,ACTIVE=2} Mode;
  typedef struct packed {bit[7:0] data;} Payload;
endpackage

interface parameter_bus #(parameter int W=8, N=3,
                          parameter type Word=bit[W-1:0]);
  Word data;
  bit [W-1:0] lanes[N];
  function Word echo(input Word value);
    return value;
  endfunction
  task exchange(input Word value, output Word result, inout int count);
    #1ns;
    data=value;
    result=data;
    count+=N;
  endtask
  modport access(inout data, lanes, import echo, exchange);
endinterface

package parameterized_vif_pkg;
  typedef virtual parameter_bus.access DefaultBus;
  typedef virtual parameter_bus#(8,3,bit[7:0]).access ExplicitDefaultBus;
  typedef virtual parameter_bus#(.W(13),.N(2)).access WideBus;
  typedef virtual parameter_bus#(.W(13),.N(2),.Word(bit[6:0])) TypedBus;
  typedef virtual parameter_bus#(13,2,parameterized_vif_types_pkg::Word) AliasBus;
  typedef virtual parameter_bus#(.Word(parameterized_vif_types_pkg::Mode)) EnumBus;
  typedef virtual parameter_bus#(.Word(parameterized_vif_types_pkg::Payload)) StructBus;
  class Owner;
    local static DefaultBus default_bus;
    local static WideBus wide_bus;
    local static TypedBus typed_bus;
    local static EnumBus enum_bus;
    local static StructBus struct_bus;
    static function void set_buses(DefaultBus a, WideBus b, TypedBus c);
      default_bus=a; wide_bus=b; typed_bus=c;
    endfunction
    static function void set_named_buses(EnumBus a, StructBus b);
      enum_bus=a; struct_bus=b;
    endfunction
    static function DefaultBus get_default(); return default_bus; endfunction
    static function ExplicitDefaultBus get_same(); return default_bus; endfunction
    static function WideBus get_wide(); return wide_bus; endfunction
    static function TypedBus get_typed(); return typed_bus; endfunction
    static function AliasBus get_alias(); return typed_bus; endfunction
    static function EnumBus get_enum(); return enum_bus; endfunction
    static function StructBus get_struct(); return struct_bus; endfunction
  endclass
endpackage
