package register_policy_pkg;
  // This class is transported as a handle, not generated as an inheritance target.
  class PacketTag;
    int number;
    function new(int number);
      this.number = number;
    endfunction
  endclass

  typedef virtual register_if.diagnostics diagnostic_bus_t;

  class RegisterPolicy;
    bit [31:0] mask;
    int calls = 0;
    int history[$];
    PacketTag packet = new(7);
    diagnostic_bus_t bus;

    function new(bit [31:0] mask);
      this.mask = mask;
    endfunction

    virtual function bit [31:0] normalize(bit [31:0] value);
      return value & mask;
    endfunction

    virtual function int calibrate(input int delta, output int observed, inout int budget);
      observed = delta;
      budget += delta;
      return budget;
    endfunction

    function PacketTag echo_packet(PacketTag value);
      return value;
    endfunction

    function diagnostic_bus_t echo_bus(diagnostic_bus_t value);
      return value;
    endfunction

    function bit same_bus(diagnostic_bus_t value);
      return value == bus;
    endfunction

    static function int word_bytes();
      return 4;
    endfunction
  endclass
endpackage
