package external_handle_test_pkg;
  class Packet;
    int packet_id;
    function new(int packet_id);
      this.packet_id = packet_id;
    endfunction
  endclass
endpackage

package constructor_handle_pkg;
  class Holder;
    external_handle_test_pkg::Packet packet;
    virtual external_bus_if.master vif;
    external_handle_test_pkg::Packet native_packet;
    virtual external_bus_if.master native_vif;
    function new(external_handle_test_pkg::Packet packet, virtual external_bus_if.master vif);
      this.packet = packet;
      this.vif = vif;
      native_packet = packet;
      native_vif = vif;
    endfunction
    function int read_value();
      return packet == null ? -1 : packet.packet_id;
    endfunction
  endclass
endpackage
