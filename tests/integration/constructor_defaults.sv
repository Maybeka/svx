package constructor_defaults_pkg;
  class Driver;
    int seed;
    string label;
    function new(int seed = 7, string label = "default-driver");
      this.seed = seed;
      this.label = label;
    endfunction
    function int get_seed(); return seed; endfunction
    function string get_label(); return label; endfunction
    task advance(input int amount); #1ns; seed += amount; endtask
  endclass
endpackage
