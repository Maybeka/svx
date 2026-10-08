package field_owner_pkg;
  class Base;
    protected int count = 11;
    protected function int get_count(); return count; endfunction
    function void set_count(int value); count = value; endfunction
  endclass
endpackage
