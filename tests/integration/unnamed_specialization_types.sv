package unnamed_specialization_pkg;
  int constructor_calls = 0;
  class Root #(type T = int, int W = 8);
    T item;
    bit [W-1:0] flags;
    function new(T value);
      constructor_calls++;
      item = value;
      flags = '1;
    endfunction
    virtual function T echo(T value);
      return value;
    endfunction
    static function int width();
      return W;
    endfunction
    static function int construction_count();
      return constructor_calls;
    endfunction
    protected static function T static_echo(T value);
      return value;
    endfunction
  endclass
  class Middle #(type T = int, int W = 8) extends Root#(T, W+1);
    function new(T value);
      super.new(value);
    endfunction
  endclass
  class ByteChild extends Middle#(byte, 4);
    function new(byte value);
      super.new(value);
    endfunction
  endclass
  class ShortChild extends Middle#(shortint unsigned, 16);
    function new(shortint unsigned value);
      super.new(value);
    endfunction
    static function int width();
      return 99;
    endfunction
  endclass
endpackage
