`include "svtypes_pkg.sv"
`include "sv/svx_pkg.sv"
`include "tests/integration/external_bus_if.sv"
`include ".tmp/source_discovery/value_types.sv"
`include "tests/integration/source_discovery_types.sv"
`include ".tmp/source_discovery/mirrors.sv"

module tb;
  external_bus_if bus();
  import svx_pkg::*;
  source_discovery_pkg::Base handle;
  source_discovery_pkg::samples_t values, observed, changed, result;
  source_discovery_pkg::dynamic_samples_t dynamic_values, dynamic_result;
  source_discovery_pkg::fixed_samples_t fixed_values, fixed_result;
  source_discovery_pkg::keyed_samples_t keyed_values, keyed_result;
  source_discovery_pkg::Packet packet_result;
  source_discovery_pkg::bytes_t byte_values, byte_result;
  source_discovery_pkg::shorts_t short_values, short_result;
  source_discovery_pkg::flags_t flag_values, flag_result;
  source_discovery_pkg::stamps_t stamp_values, stamp_result;
  source_value_pkg::ValuePacket_t packet_value, packet_value_result;
  virtual external_bus_if.master vif_result;
  longint unsigned receiver_id;
  initial begin
    svx_init();
    svx_load("tests.integration.source_discovery_test");
    svx_start("source_discovery.create");
    `SVX_GET_OBJECT(source_discovery_pkg::Base, "source_discovery.instance", handle)
    receiver_id = svx_inheritance_registry::published_object_ids["source_discovery.instance"];
    if (handle.check(3) != 112)
      $fatal(1, "source-discovered virtual callback or shared field failed");
    if (handle.echo_byte(-12) != -12 || handle.echo_short(-1234) != -1234 ||
        handle.echo_unsigned(32'hfedcba98) != 32'hfedcba98)
      $fatal(1, "source-discovered integer width or signedness failed");
    if (handle.echo_integer(32'h000000xz) !== 32'h000000xz ||
        handle.echo_time(64'hx000z00000000001) !== 64'hx000z00000000001)
      $fatal(1, "source-discovered integer/time lost X/Z states");
    if (handle.echo_shortreal(1.25) != 1.25 || handle.echo_signed_bit(-1) != -1)
      $fatal(1, "source-discovered floating or signed scalar failed");
    if (handle.flags !== 32'b00000000000000000000000000zx0001)
      $fatal(1, "source-discovered integer field lost X/Z states");
    byte_values = '{-128, -1, 127};
    byte_result = handle.echo_bytes(byte_values);
    if (byte_result.size() != 3 || byte_result[0] != -128 || byte_result[1] != -1 || byte_result[2] != 127)
      $fatal(1, "source-discovered byte queue changed signed elements");
    short_values = new[2];
    short_values[0] = 0;
    short_values[1] = 16'hffff;
    short_result = handle.echo_shorts(short_values);
    if (short_result.size() != 2 || short_result[0] != 0 || short_result[1] != 16'hffff)
      $fatal(1, "source-discovered shortint array changed unsigned elements");
    flag_values = '{32'h000000xz, 32'h7};
    flag_result = handle.echo_flags(flag_values);
    if (flag_result[0] !== 32'h000000xz || flag_result[1] !== 32'h7)
      $fatal(1, "source-discovered integer array lost X/Z states");
    stamp_values["stamp"] = 64'hx000z00000000001;
    stamp_result = handle.echo_stamps(stamp_values);
    if (stamp_result.num() != 1 || !stamp_result.exists("stamp") ||
        stamp_result["stamp"] !== 64'hx000z00000000001)
      $fatal(1, "source-discovered time associative array lost key or X/Z states");
    if (handle.echo_operation(source_value_pkg::RUN) != source_value_pkg::RUN ||
        handle.operation != source_value_pkg::RUN)
      $fatal(1, "source-discovered enum lost its value");
    packet_value = '{tag: 8'ha5, flags: 4'b0zx1};
    packet_value_result = handle.echo_value_packet(packet_value);
    if (packet_value_result.tag != 8'ha5 || packet_value_result.flags !== 4'b0zx1)
      $fatal(1, "source-discovered struct lost member values or X/Z states");
    values = '{4, 5};
    changed = '{6};
    result = handle.transform(values, observed, changed);
    if (result.size() != 3 || result[0] != 4 || result[1] != 5 || result[2] != 100)
      $fatal(1, "source-discovered collection return failed");
    if (observed.size() != 4 || observed[0] != 4 || observed[1] != 5 || observed[2] != 30 || observed[3] != 200)
      $fatal(1, "source-discovered collection output failed");
    if (changed.size() != 3 || changed[0] != 6 || changed[1] != 40 || changed[2] != 300)
      $fatal(1, "source-discovered collection inout failed");
    dynamic_values = new[2];
    dynamic_values[0] = 7;
    dynamic_values[1] = 8;
    dynamic_result = handle.dynamic_copy(dynamic_values);
    if (dynamic_result.size() != 3 || dynamic_result[0] != 7 || dynamic_result[1] != 8 || dynamic_result[2] != 101)
      $fatal(1, "source-discovered dynamic array call failed");
    fixed_values = '{9, 10};
    fixed_result = handle.fixed_copy(fixed_values);
    if (fixed_result[0] != 9 || fixed_result[1] != 112)
      $fatal(1, "source-discovered fixed array call failed");
    keyed_values["sv"] = 11;
    keyed_result = handle.keyed_copy(keyed_values);
    if (keyed_result.num() != 2 || !keyed_result.exists("sv") || keyed_result["sv"] != 11 ||
        !keyed_result.exists("python") || keyed_result["python"] != 103)
      $fatal(1, "source-discovered associative array call failed");
    $display("SOURCE_DISCOVERY_COLLECTION_PASS");
    packet_result = handle.echo_packet(handle.packet);
    if (packet_result != handle.packet || packet_result.packet_id != 41)
      $fatal(1, "source-discovered unmapped class handle changed identity");
    handle.vif = bus;
    bus.ready = 1;
    vif_result = handle.echo_vif(handle.vif);
    if (vif_result != handle.vif)
      $fatal(1, "source-discovered virtual interface changed identity");
    if (bus.read() !== 8'h52)
      $fatal(1, "source-discovered virtual interface lost access: data=%h", bus.read());
    if (handle.samples.size() != 3 || handle.samples[0] != 5 || handle.samples[2] != 7)
      $fatal(1, "source-discovered queue storage failed");
    handle.samples.push_back(8);
    handle.count = 13;
    svx_start("source_discovery.close");
    if (svx_inheritance_registry::objects.exists(receiver_id) ||
        svx_inheritance_registry::published_object_ids.exists("source_discovery.instance"))
      $fatal(1, "source discovery leaked an SV receiver");
    svx_shutdown();
    $display("SOURCE_DISCOVERY_PASS");
    $finish;
  end
endmodule
