// SPDX-License-Identifier: Apache-2.0
program sv_example_program_owner #(parameter int WIDTH=8);
  import svx_pkg::*;
  int owner_state=1;
  class Base;
    int count;
    function new(int seed);count=seed;endfunction
    virtual function int status();return count+owner_state;endfunction
    static function int inherited_owner();return owner_state+WIDTH;endfunction
  endclass
  class Driver extends Base;
    int created_owner;
    bit[WIDTH-1:0] mask;
    function new(int seed);super.new(seed);created_owner=owner_state;endfunction
    function int owner();return owner_state;endfunction
    function int width();return $bits(mask);endfunction
    function void update_owner(int value);owner_state=value;endfunction
    task advance(input int value,output int previous,inout int total);
      #1ns;previous=count;count=value;total+=value;
    endtask
    static function void configure(int value);owner_state=value;endfunction
    static function int read_owner();return owner_state;endfunction
    static function void verify_published(string name,int expected,int original_owner);
      Driver value;
      `SVX_GET_OBJECT(Driver,name,value)
      if(value.created_owner!=original_owner)$fatal(1,"program constructor owner");
      if(value.status()!=expected)$fatal(1,"program virtual callback");
    endfunction
  endclass
endprogram
