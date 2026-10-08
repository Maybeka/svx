package python_multi_final_pkg;
  class Grandchild extends svx_proxy_python_unit_source::Derived;
    int e_value = 500;
    int observed_derived;
    function new(int e_seed);
      super.new(e_seed);
      observed_derived = own_value;
    endfunction
    virtual function int check(int delta);
      return super.check(delta) + e_value;
    endfunction
    function int fixed(int delta); return count + delta + 700; endfunction
    function int observed_python(); return observed_derived; endfunction
  endclass
endpackage
