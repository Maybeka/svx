package python_unit_pkg;
  class Child extends svx_proxy_python_unit_source::Root;
    int child_value = 100;
    int observed_root;
    function new(int child_seed);
      super.new(child_seed);
      observed_root = count;
    endfunction
    virtual function int check(int delta);
      return super.check(delta) + child_value;
    endfunction
    function int fixed(int delta);
      return count + delta + 300;
    endfunction
    function int observed_value();
      return observed_root;
    endfunction
  endclass
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
    function int fixed(int delta);
      return count + delta + 700;
    endfunction
    function int observed_python();
      return observed_derived;
    endfunction
  endclass
endpackage
