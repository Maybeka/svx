package example_packet_pkg;
  class Packet;
    int unsigned identifier;

    function new(int unsigned identifier = 0);
      this.identifier = identifier;
    endfunction
  endclass

  class TaggedPacket extends Packet;
    string tag;

    function new(int unsigned identifier, string tag);
      super.new(identifier);
      this.tag = tag;
    endfunction
  endclass
endpackage
