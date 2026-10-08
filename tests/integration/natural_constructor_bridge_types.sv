package natural_bridge_pkg;
  class Packet;
    int token = 23;
  endclass
  class A;
    int count;
    string label;
    Packet packet;
    function new(int seed, string label, Packet packet);
      count = seed;
      this.label = label;
      this.packet = packet;
    endfunction
  endclass
endpackage
