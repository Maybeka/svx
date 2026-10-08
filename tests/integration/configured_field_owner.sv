`ifdef SVX_FIELD_ENABLED
`include "sv_field_owner.sv"
`else
package field_owner_pkg;
  class Base;
    protected bit [7:0] count;
    protected function bit [7:0] get_count();
      return count;
    endfunction
    function void set_count(bit [7:0] value);
      count = value;
    endfunction
  endclass
endpackage
`endif
