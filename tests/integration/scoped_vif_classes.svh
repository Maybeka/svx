typedef virtual scoped_bus_if.master Bus;
typedef Bus Buses[$];
class Owner;
  Bus bus;
  Buses buses;
  function new(Bus bus);
    this.bus = bus;
  endfunction
  static function Bus get_bus(int index);
    Bus result;
    if (index == 0) result = $root.tb.bus0;
    else result = $root.tb.bus1;
    return result;
  endfunction
  virtual function Bus echo(Bus value);
    return value;
  endfunction
  task exchange(input Bus value, output Bus previous, inout Bus changed);
    #1ns;
    previous = bus;
    bus = value;
    changed = value;
  endtask
endclass
class Consumer;
  static function Bus echo(Bus value);
    return value;
  endfunction
endclass
