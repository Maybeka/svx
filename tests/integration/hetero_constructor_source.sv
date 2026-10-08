package hetero_child_pkg;
  class Child extends svx_proxy_hetero_constructor_source::Root;
    int child_value = 100;
    int observed_root;
    string actual_label;
    function new(int child_seed, string label);
      super.new(child_seed + 10);
      observed_root = count;
      actual_label = label;
    endfunction
    virtual function int check(int delta); return super.check(delta) + child_value; endfunction
    function int fixed(int delta); return count + delta + 300; endfunction
    function int observed_value(); return observed_root; endfunction
  endclass
endpackage

package hetero_final_pkg;
  class Grandchild extends svx_proxy_hetero_constructor_source::Derived;
    int e_value = 500;
    int observed_derived;
    function new();
      super.new(7, "abc");
      observed_derived = own_value;
    endfunction
    virtual function int check(int delta); return super.check(delta) + e_value; endfunction
    function int fixed(int delta); return count + delta + 700; endfunction
    function int observed_python(); return observed_derived; endfunction
  endclass
endpackage
