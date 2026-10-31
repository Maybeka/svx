// SPDX-License-Identifier: Apache-2.0
module sv_example_generate_owner #(parameter int WIDTH=8);
  import svx_pkg::*;
  int owner_state;
  for(genvar LANE=0;LANE<2;LANE++)begin:lane
    localparam int INDEX=LANE;
    localparam int NATIVE_WIDTH=WIDTH+LANE;
    if(1)begin:active
      localparam int LANE=99;
      class Base;
        int count;
        function new(int seed);count=seed;endfunction
        virtual function int status();return count+owner_state+INDEX;endfunction
        static function int inherited_owner();return owner_state+WIDTH+INDEX;endfunction
      endclass
      class Driver extends Base;
        int created_owner;
        bit[NATIVE_WIDTH-1:0] mask;
        function new(int seed);
          super.new(seed);
          created_owner=owner_state;
        endfunction
        function int owner();return owner_state;endfunction
        function int width();return $bits(mask);endfunction
        function int lane_index();return INDEX;endfunction
        function void update_owner(int value);owner_state=value;endfunction
        task advance(input int value,output int previous,inout int total);
          #1ns;previous=count;count=value;total+=value;
        endtask
        static function int owner_index();return owner_state+INDEX;endfunction
      endclass
      task automatic check_published(string name,int expected,int original_owner);
        Driver value;
        `SVX_GET_OBJECT(Driver,name,value)
        if(value.created_owner!=original_owner)$fatal(1,"generate constructor owner");
        if(value.status()!=expected)$fatal(1,"generate virtual callback");
      endtask
    end:active
  end:lane
endmodule
