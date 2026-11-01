package a_b;
  class C;
    int value;
    function new(int value);
      this.value = value;
    endfunction
  endclass
endpackage

package a;
  class b_C;
    int value;
    function new(int value);
      this.value = value;
    endfunction
  endclass
endpackage

package collision_api;
  typedef a_b::C LeftItems[$];
  typedef a::b_C RightItems[$];
  class Owner;
    a_b::C left;
    a::b_C right;
    LeftItems left_items;
    RightItems right_items;

    function new(a_b::C left, a::b_C right);
      this.left = left;
      this.right = right;
    endfunction

    static function a_b::C make_left(int value);
      a_b::C result = new(value);
      return result;
    endfunction

    static function a::b_C make_right(int value);
      a::b_C result = new(value);
      return result;
    endfunction

    virtual function a_b::C echo_left(a_b::C value);
      return value;
    endfunction

    function a::b_C echo_right(a::b_C value);
      return value;
    endfunction

    function LeftItems echo_left_items(LeftItems values);
      return values;
    endfunction

    function RightItems echo_right_items(RightItems values);
      return values;
    endfunction

    function int read_left(a_b::C value);
      return value == null ? -1 : value.value;
    endfunction

    function int read_right(a::b_C value);
      return value == null ? -1 : value.value;
    endfunction
  endclass
endpackage
