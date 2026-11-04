package class_enum_arrays_pkg;
  class Driver;
    typedef enum bit [2:0] { A_IDLE=0, A_RUN=1, A_DONE=4 } first_t;
    typedef enum bit [2:0] { B_IDLE=0, B_RUN=2, B_DONE=5 } second_t;
    first_t first[3];
    second_t second[3];

    function new();
      foreach (first[i]) first[i] = A_IDLE;
      foreach (second[i]) second[i] = B_DONE;
    endfunction
    function int first_at(input int index); return int'(first[index]); endfunction
    function int second_at(input int index); return int'(second[index]); endfunction
    function void set_values(input first_t a[3], input second_t b[3]);
      first = a;
      second = b;
    endfunction
    function void get_values(output first_t a[3], output second_t b[3]);
      a = first;
      b = second;
    endfunction
  endclass
endpackage
