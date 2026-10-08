package source_discovery_pkg;
  class PacketTemplate #(type IDType=shortint);
    IDType packet_id;
    function new(input IDType packet_id);
      this.packet_id = packet_id;
    endfunction
  endclass
  typedef PacketTemplate#(int) Packet;
  typedef int count_t;
  typedef int samples_t[$];
  typedef int dynamic_samples_t[];
  typedef int fixed_samples_t[2];
  typedef int keyed_samples_t[string];
  typedef virtual external_bus_if.master bus_handle_t;
  typedef byte bytes_t[$];
  typedef shortint unsigned shorts_t[];
  typedef integer flags_t[2];
  typedef time stamps_t[string];
  typedef source_value_pkg::Operation operation_t;
  class BaseTemplate #(type SeedType=shortint, int DEFAULT_COUNT=100);
    count_t count;
    int samples[$] = '{1, 2};
    Packet packet = new(41);
    virtual external_bus_if.master vif;
    integer flags;
    operation_t operation;
    function new(input SeedType seed);
      count = seed + DEFAULT_COUNT;
    endfunction
    virtual function dynamic_samples_t dynamic_copy(input dynamic_samples_t values);
      return values;
    endfunction
    virtual function fixed_samples_t fixed_copy(input fixed_samples_t values);
      return values;
    endfunction
    virtual function keyed_samples_t keyed_copy(input keyed_samples_t values);
      return values;
    endfunction
    virtual function Packet echo_packet(input Packet value);
      return value;
    endfunction
    virtual function bus_handle_t echo_vif(input bus_handle_t value);
      return value;
    endfunction
    virtual function count_t check(input count_t value);
      return count + value;
    endfunction
    virtual function byte echo_byte(input byte value);
      return value;
    endfunction
    virtual function shortint echo_short(input shortint value);
      return value;
    endfunction
    virtual function int unsigned echo_unsigned(input int unsigned value);
      return value;
    endfunction
    virtual function integer echo_integer(input integer value);
      return value;
    endfunction
    virtual function time echo_time(input time value);
      return value;
    endfunction
    virtual function shortreal echo_shortreal(input shortreal value);
      return value;
    endfunction
    virtual function bit signed echo_signed_bit(input bit signed value);
      return value;
    endfunction
    virtual function bytes_t echo_bytes(input bytes_t values);
      return values;
    endfunction
    virtual function shorts_t echo_shorts(input shorts_t values);
      return values;
    endfunction
    virtual function flags_t echo_flags(input flags_t values);
      return values;
    endfunction
    virtual function stamps_t echo_stamps(input stamps_t values);
      return values;
    endfunction
    virtual function operation_t echo_operation(input operation_t value);
      return value;
    endfunction
    virtual function source_value_pkg::ValuePacket_t echo_value_packet(input source_value_pkg::ValuePacket_t value);
      return value;
    endfunction
    virtual function samples_t transform(input samples_t values,
                                          output samples_t observed,
                                          inout samples_t changed);
      observed = values;
      observed.push_back(30);
      changed.push_back(40);
      return values;
    endfunction
  endclass
  typedef BaseTemplate#(int, 0) Base;
endpackage
