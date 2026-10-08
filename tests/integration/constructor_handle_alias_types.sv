package external_handle_test_pkg;
  class Packet #(int N = 8);
    int packet_id;
    function new(int packet_id);
      this.packet_id = packet_id;
    endfunction
  endclass
endpackage

package constructor_handle_pkg;
  import external_handle_test_pkg::*;
  typedef Packet#(8) packet_alias_t;
  typedef virtual external_bus_if.master bus_alias_t;
  class Holder;
    Packet packet;
    virtual external_bus_if.master vif;
    packet_alias_t native_packet;
    bus_alias_t native_vif;
    function new(Packet packet, virtual external_bus_if.master vif);
      this.packet = packet;
      this.vif = vif;
      native_packet = packet;
      native_vif = vif;
    endfunction
    function int read_value();
      return packet == null ? -1 : packet.packet_id;
    endfunction
    function packet_alias_t echo_packet(input packet_alias_t value);
      return value;
    endfunction
  endclass
endpackage
