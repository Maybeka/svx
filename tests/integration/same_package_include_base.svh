`define SVX_INCLUDE_EXTRA 100
class A;
  localparam string declaration_file = `__FILE__;
  localparam int declaration_line = `__LINE__;
  int count = 11;
  static int allocations;
  function new();
    allocations++;
  endfunction
  virtual function int check();
    return count;
  endfunction
  protected static function int scale();
    return 22;
  endfunction
endclass
