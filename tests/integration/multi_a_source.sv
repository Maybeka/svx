package multi_a_pkg;
  class A;
    int count = 11;
    static int allocations;
    function new(); allocations++; endfunction
    virtual function int check(); return count; endfunction
    protected static function int scale(); return 22; endfunction
  endclass
endpackage
