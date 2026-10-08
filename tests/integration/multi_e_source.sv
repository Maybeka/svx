package multi_e_pkg;
  class E extends svx_proxy_multi_unit_source::D;
    int e_value = 500;
    int observed_d;
    function new(); super.new(); observed_d = own; endfunction
    virtual function int check(); return super.check() + e_value; endfunction
    function int observed_python(); return observed_d; endfunction
  endclass
endpackage
