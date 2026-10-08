package multi_c_pkg;
  class C extends svx_proxy_multi_unit_source::B;
    int extra = 100;
    int observed;
    function new(); super.new(); observed = retry; endfunction
    virtual function int check(); return super.check() + extra; endfunction
    function int observed_value(); return observed; endfunction
  endclass
endpackage
