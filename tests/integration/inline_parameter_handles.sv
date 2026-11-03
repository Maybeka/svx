// SPDX-License-Identifier: Apache-2.0
package inline_types_pkg;
  class Packet #(int WIDTH = 8);
    int tag;
  endclass
  class Typed #(type T = int);
    T value;
  endclass
  class Config;
    typedef enum bit [1:0] { IDLE = 0, ACTIVE = 2 } Mode;
  endclass
  typedef Config::Mode Mode;
endpackage

package inline_alias_pkg;
  typedef inline_types_pkg::Mode Mode;
endpackage

package inline_drivers_pkg;
  import inline_types_pkg::*;
  import inline_alias_pkg::Mode;
  class Base;
    static int excluded_noise;
    Mode mode;
  endclass
  class Holder;
    Packet#(16) item;
    function new(Packet#(16) value);
      item = value;
    endfunction
    function int tag();
      return item.tag;
    endfunction
  endclass
  class Driver extends Base;
    function Packet make_default(int tag);
      Packet item = new;
      item.tag = tag;
      return item;
    endfunction
    function Packet#(16) make_wide(int tag);
      Packet#(16) item = new;
      item.tag = tag;
      return item;
    endfunction
    function int default_tag(Packet item);
      return item == null ? -1 : item.tag;
    endfunction
    function int wide_tag(Packet#(.WIDTH(16)) item);
      return item == null ? -1 : item.tag;
    endfunction
    function Packet#(16) echo(Packet#(16) item);
      return item;
    endfunction
    function int explicit_default_tag(Packet#(8) item);
      return item.tag;
    endfunction
    function void exchange(input Packet#(16) item, output Packet#(16) result,
                           inout Packet#(16) changed);
      result = item;
      changed = item;
    endfunction
    function Typed#(bit [7:0]) make_typed();
      Typed#(bit [7:0]) item = new;
      item.value = 37;
      return item;
    endfunction
    function int typed_value(Typed#(bit [7:0]) item);
      return item.value;
    endfunction
    function Typed#(Packet#(16)) make_nested();
      Typed#(Packet#(16)) item = new;
      item.value = new;
      item.value.tag = 43;
      return item;
    endfunction
    function int nested_value(Typed#(Packet#(16)) item);
      return item.value.tag;
    endfunction
    function Mode echo_mode(Mode value);
      return value;
    endfunction
  endclass
endpackage
