// SPDX-License-Identifier: Apache-2.0
package generic_constants_types_pkg;
  typedef enum bit [1:0] {OFF = 0, ON = 2} State;
  typedef struct packed {bit [3:0] code; State state;} Item;
endpackage

package generic_class_constants_pkg;
  class Config #(int WIDTH = 8, type T = bit [3:0]);
    typedef enum bit [WIDTH-1:0] {IDLE = WIDTH'(0), READY = WIDTH'(3)} Mode;
    typedef struct packed {logic [WIDTH-1:0] data; Mode mode;} Packet;
    localparam int COUNT = WIDTH + 1;
    localparam Mode DEFAULT_MODE = READY;
    localparam Packet DEFAULT_PACKET = '{data:'x, mode:READY};
    localparam T DEFAULT_ITEM = '0;
    int value;
    function new(); value = WIDTH; endfunction
    static function int get_width(); return WIDTH; endfunction
    static function Packet get_packet(); return DEFAULT_PACKET; endfunction
    static function T get_item(); return DEFAULT_ITEM; endfunction
    function int get_value(); return value; endfunction
    function Mode echo_mode(input Mode arg); return arg; endfunction
    virtual function int score(input int arg); return arg + WIDTH; endfunction
    task pass_packet(input Packet arg, output Packet result, inout int count);
      #1ns;
      result = arg;
      count++;
    endtask
  endclass
  typedef Config#(9, generic_constants_types_pkg::Item) Narrow;
  typedef Config#(70, generic_constants_types_pkg::Item) Wide;
  typedef Narrow Same;
  class Child extends Narrow;
    localparam int CHILD_COUNT = WIDTH + 2;
  endclass
  function automatic Narrow::Mode narrow_echo(input Narrow::Mode arg);
    return arg;
  endfunction
  function automatic Wide::Packet wide_packet();
    return Wide::DEFAULT_PACKET;
  endfunction
  function automatic Config#()::Packet default_packet();
    return Config#()::DEFAULT_PACKET;
  endfunction
  task automatic wide_echo(input Wide::Packet arg, output Wide::Packet result);
    #1ns;
    result = arg;
  endtask
endpackage
