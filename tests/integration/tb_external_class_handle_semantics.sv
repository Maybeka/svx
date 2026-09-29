package external_handle_semantics_pkg;
  class Packet;
    int unsigned packet_id;

    function new(int unsigned packet_id = 0);
      this.packet_id = packet_id;
    endfunction
  endclass

  class TaggedPacket extends Packet;
    string tag;

    function new(int unsigned packet_id, string tag);
      super.new(packet_id);
      this.tag = tag;
    endfunction
  endclass

  class PacketSink;
    Packet retained;

    task accept(input Packet packet);
      retained = packet;
    endtask

    function bit same_handle(input Packet candidate);
      return retained == candidate;
    endfunction
  endclass
endpackage

module tb;
  import external_handle_semantics_pkg::*;

  initial begin
    Packet as_base;
    TaggedPacket source;
    TaggedPacket restored;
    PacketSink sink;

    source = new(17, "from-derived");
    as_base = source;
    sink = new();
    sink.accept(as_base);
    if (!sink.same_handle(source)) $fatal(1, "class handle identity was not retained");
    if (!$cast(restored, sink.retained)) $fatal(1, "base handle did not preserve dynamic type");
    if (restored.packet_id != 17 || restored.tag != "from-derived") begin
      $fatal(1, "restored class handle has incorrect state");
    end
    sink.accept(null);
    if (sink.retained != null) $fatal(1, "null class handle was not retained");

    $display("EXTERNAL_CLASS_HANDLE_SEMANTICS_PASS");
    $finish;
  end
endmodule
