package same_package_pkg;
  class A;
    int count = 11;
    static int allocations;
    function new();
      allocations++;
    endfunction
    virtual function int check();
      return count;
    endfunction
    protected static function int scale();
      return 22;
    endfunction
  endclass
  class C extends svx_proxy_same_module_source::B;
    int extra = 100;
    int observed;
    function new();
      super.new();
      observed = retry;
    endfunction
    virtual function int check();
      return super.check() + extra;
    endfunction
    function int observed_value();
      return observed;
    endfunction
  endclass
  class E extends svx_proxy_same_module_source::D;
    int e_value = 500;
    int observed_d;
    function new();
      super.new();
      observed_d = own;
    endfunction
    virtual function int check();
      return super.check() + e_value;
    endfunction
    function int observed_python();
      return observed_d;
    endfunction
  endclass
endpackage
