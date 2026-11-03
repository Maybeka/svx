package editable_static_pkg;
  function int package_scale(input int value);
    return value * 5;
  endfunction
  class Driver;
    static function int svx_core_Driver_scale();
      return 99;
    endfunction
    static function int scale(input int value);
      return value * 3;
    endfunction
    static task wait_once();
      #2ns;
    endtask
  endclass
endpackage
