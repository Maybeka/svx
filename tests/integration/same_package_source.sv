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

  // The tool must not rewrite comments or literals mentioning the public type.
  // class C extends svx_proxy_same_package_test::B
  class C extends svx_proxy_same_package_test::B;
    localparam string declaration_file = `__FILE__;
    localparam int declaration_line = `__LINE__;
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
endpackage
