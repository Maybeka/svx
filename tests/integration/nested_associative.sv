package nested_associative_pkg;
  class Driver;
    int values[int][int];

    function new();
      values[1][2] = 12;
      values[1][3] = 13;
      values[4][5] = 45;
    endfunction

    function bit check();
      return values.num() == 3 && values[1].num() == 1 && values[1][8] == 18 &&
             values[4][5] == 45 && values[7][8] == 78 && !values.exists(99);
    endfunction
  endclass
endpackage
