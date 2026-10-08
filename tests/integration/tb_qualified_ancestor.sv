package qualified_ancestor_pkg;
  class A;
    virtual function int check();
      return 1;
    endfunction
  endclass
  class Middle extends A;
    protected int value = 300;
    virtual function int check();
      return super.check() + value;
    endfunction
    protected function int read_value();
      return value;
    endfunction
  endclass
  class C extends Middle;
    virtual function int check();
      return super.check() + 100;
    endfunction
  endclass
  class Helper extends C;
    function int qualified_check();
      return qualified_ancestor_pkg::Middle::check();
    endfunction
    function int qualified_read();
      return qualified_ancestor_pkg::Middle::read_value();
    endfunction
  endclass
endpackage

module tb;
  initial begin
    qualified_ancestor_pkg::Helper value = new();
    if (value.check() != 401 || value.qualified_check() != 301 || value.qualified_read() != 300)
      $fatal(1, "qualified ancestor call selected the wrong source implementation");
    $display("QUALIFIED_ANCESTOR_PASS");
    $finish;
  end
endmodule
