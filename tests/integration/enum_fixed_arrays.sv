`ifndef ENUM_FIXED_DEPTH
`define ENUM_FIXED_DEPTH 3
`endif

package enum_fixed_a;
  class Codes;
    typedef enum bit [1:0] { IDLE=0, RUN=1, DONE=3 } State;
  endclass
  typedef Codes::State state_alias_t;
endpackage

package enum_fixed_b;
  class Codes;
    typedef enum bit [1:0] { IDLE=0, RUN=1, DONE=3 } State;
  endclass
  typedef Codes::State state_alias_t;
endpackage

package enum_fixed_wide;
  typedef enum bit [8:0] { LOW=0, HIGH=257, LAST=511 } State;
endpackage

package enum_fixed_arrays_pkg;
  typedef enum_fixed_a::state_alias_t first_alias_t;
  typedef first_alias_t first_t;
  typedef enum_fixed_b::state_alias_t second_t;
  typedef enum_fixed_wide::State wide_t;
  typedef enum bit [1:0] { QUIET=0, ACTIVE=2 } local_t;
  typedef first_t first_result_t[`ENUM_FIXED_DEPTH];
  typedef second_t second_result_t[`ENUM_FIXED_DEPTH];
  typedef struct {
    first_t first[`ENUM_FIXED_DEPTH];
    second_t second[`ENUM_FIXED_DEPTH];
    wide_t wide[2];
    local_t local_values[2];
  } Bundle;

  class Base;
    int ignored = 99;
    first_t inherited_states[2];
    function new();
      inherited_states[0] = enum_fixed_a::Codes::IDLE;
      inherited_states[1] = enum_fixed_a::Codes::DONE;
    endfunction
  endclass

  class Driver extends Base;
    first_t first[`ENUM_FIXED_DEPTH];
    second_t second[`ENUM_FIXED_DEPTH];
    wide_t wide[2];
    local_t local_values[2];
    second_t grid[2][2];
    Bundle bundle;
    function new();
      super.new();
      foreach (first[i]) first[i] = enum_fixed_a::Codes::IDLE;
      foreach (second[i]) second[i] = enum_fixed_b::Codes::DONE;
      wide[0] = enum_fixed_wide::HIGH;
      wide[1] = enum_fixed_wide::LAST;
      local_values[0] = QUIET;
      local_values[1] = ACTIVE;
      foreach (grid[i,j]) grid[i][j] = enum_fixed_b::Codes::RUN;
      bundle.first = first;
      bundle.second = second;
      bundle.wide = wide;
      bundle.local_values = local_values;
    endfunction
    function int depth(); return `ENUM_FIXED_DEPTH; endfunction
    function first_result_t echo_first(input first_t values[`ENUM_FIXED_DEPTH]);
      return values;
    endfunction
    function second_result_t echo_second(input second_t values[`ENUM_FIXED_DEPTH]);
      return values;
    endfunction
    function void exchange(input first_t request[`ENUM_FIXED_DEPTH],
                           input second_t previous[`ENUM_FIXED_DEPTH],
                           output second_t result[`ENUM_FIXED_DEPTH],
                           inout wide_t current[2]);
      result = previous;
      if (request[0] == enum_fixed_a::Codes::RUN)
        result[0] = enum_fixed_b::Codes::IDLE;
      current[0] = enum_fixed_wide::LAST;
      current[1] = enum_fixed_wide::HIGH;
    endfunction
    function Bundle echo_bundle(input Bundle value); return value; endfunction
    function int first_at(input int index); return int'(first[index]); endfunction
    function int second_at(input int index); return int'(second[index]); endfunction
  endclass
endpackage
