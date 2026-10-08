package signature_types_pkg;
  typedef int count_t;

  class Base #(type T = count_t, int N = 4);
    T count;
    function new(input T seed);
      count = seed;
    endfunction

    virtual function T check(input logic [N-1:0] value);
      return T'(value) + N;
    endfunction
  endclass

  class Hosted extends Base#(int, 8);
    function new(input int seed);
      super.new(seed);
    endfunction
  endclass
endpackage
