class C extends svx_proxy_same_package_test::B;
  localparam string declaration_file = `__FILE__;
  localparam int declaration_line = `__LINE__;
  int extra = `SVX_INCLUDE_EXTRA;
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
`undef SVX_INCLUDE_EXTRA
