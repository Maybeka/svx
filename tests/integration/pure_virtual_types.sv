package pure_virtual_pkg;
  virtual class Base;
    pure virtual function int check(input int value);
    pure virtual task update(input int delta, inout int value, output int observed);
  endclass
endpackage
