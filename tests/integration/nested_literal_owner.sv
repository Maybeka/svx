package same_package_pkg;
  interface class nested_literal_factory;
    pure virtual function void spawn();
  endclass
  class A;
    int count = 11;
    static int allocations;
    static nested_literal_factory nested_factory;
    static bit spawn_nested;
    function new();
      int early;
      allocations++;
      if (spawn_nested) begin
        spawn_nested = 0;
        nested_factory.spawn();
      end
      early = check();
      if (early != 11) $fatal(1, "nested literal changed outer initial state");
    endfunction
    virtual function int check(); return count; endfunction
    protected static function int scale(); return 22; endfunction
  endclass
  class C extends svx_proxy_same_package_test::B;
    int extra = 100;
    int observed;
    function new(); super.new(); observed = retry; endfunction
    virtual function int check(); return super.check() + extra; endfunction
    function int observed_value(); return observed; endfunction
  endclass
endpackage
