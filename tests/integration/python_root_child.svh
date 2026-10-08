class Child extends Root;
  int child_value = 100;
  int observed_root;
  function new(int child_seed, longint unsigned object_id = 0);
    super.new(child_seed, object_id);
    observed_root = count;
  endfunction
  virtual function int check(int delta);
    return super.check(delta) + child_value;
  endfunction
  function int base_check(int delta);
    return super.check(delta);
  endfunction
  function int fixed(int delta);
    return count + delta + 300;
  endfunction
  function int observed_value();
    return observed_root;
  endfunction
  static function int scale(int delta);
    return delta * 4;
  endfunction
endclass
