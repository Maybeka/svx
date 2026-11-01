package class_constants_pkg;
  class Limits;
    typedef enum bit [2:0] {IDLE = 0, READY = 5} Mode;
    typedef struct packed {bit [7:0] tag; Mode mode; logic [3:0] flags;} Packet;
    parameter int WIDTH = 8;
    localparam int NEGATIVE = -4;
    localparam Mode DEFAULT_MODE = READY;
    localparam Packet DEFAULT_PACKET = '{tag:8'h91, mode:READY, flags:4'b10xz};
    localparam int TABLE[3] = '{1, -2, 3};
    localparam int bytes = 4;
    class Nested;
      localparam string LABEL = "nested";
      localparam int DEPTH = WIDTH + 3;
    endclass
    int value;
    function new(); value = WIDTH; endfunction
    static function int get_width(); return WIDTH; endfunction
    static function Packet get_packet(); return DEFAULT_PACKET; endfunction
    static function int get_table(int index); return TABLE[index]; endfunction
    function Mode get_default(); return DEFAULT_MODE; endfunction
    function int get_value(); return value; endfunction
  endclass
  class Derived extends Limits;
    localparam int COUNT = WIDTH * 2;
  endclass
  typedef Limits Alias;
  class _svx_values;
    localparam int bytes = 7;
  endclass
endpackage

class UnitLimits;
  localparam int WIDTH = 12;
  class Nested;
    localparam int COUNT = WIDTH + 1;
  endclass
endclass

package generic_constants_pkg;
  class Generic #(int WIDTH = 8);
    localparam int COUNT = WIDTH + 1;
  endclass
endpackage
