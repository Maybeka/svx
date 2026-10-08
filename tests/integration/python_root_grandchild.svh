class Grandchild extends DerivedProxy;
  int e_value = 500;
  int observed_derived;
  function new(int e_seed, longint unsigned object_id = 0);
    super.new(e_seed, object_id);
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
