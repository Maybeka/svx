package same_package_pkg;
  class A;
    int count = 11;
    static int allocations;
    function new(); allocations++; endfunction
    virtual function int check(); return count; endfunction
    protected static function int scale(); return 22; endfunction
  endclass
  class C extends svx_proxy_field_default_stage_test::B;
    int extra = 100;
    int observed;
    function new();
      super.new();
      observed = retry;
    endfunction
    virtual function int check(); return super.check() + extra; endfunction
    function int observed_value(); return observed; endfunction
  endclass
endpackage
