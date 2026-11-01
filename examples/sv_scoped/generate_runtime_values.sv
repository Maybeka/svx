// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`include "sv/svx_defs.svh"

module generate_values #(int W=8);
  import svx_pkg::*;
  for (genvar i=0; i<1; i++) begin: lane
    class Driver;
      typedef enum bit[W-1:0] {ZERO=0, ONE=1} Mode;
      typedef struct packed {Mode mode; logic[W-1:0] data;} Payload;
      typedef bit[W-1:0] Word;
      typedef Mode Modes[$];
      typedef Payload Packets[2];
      typedef Payload Samples[];
      typedef Payload PacketMap[string];
      typedef Payload History[$];
      typedef History Groups[string];

      Mode mode;
      Payload payload;
      Modes modes;
      Packets packets;
      Samples samples;
      PacketMap by_name;
      Groups groups;

      function new(Mode initial_mode); mode=initial_mode; endfunction
      virtual function Mode echo(Mode value); mode=value; return mode; endfunction
      virtual function Payload echo_payload(Payload value); payload=value; return payload; endfunction
      virtual function Packets echo_packets(Packets values); return values; endfunction
      function Modes current_modes(); return modes; endfunction
      function Payload current_payload(); return payload; endfunction
      function Packets current_packets(); return packets; endfunction
      function Samples current_samples(); return samples; endfunction
      function PacketMap current_by_name(); return by_name; endfunction
      function Groups current_groups(); return groups; endfunction
      static function Mode static_echo(Mode value); return value; endfunction
      task advance(input Mode value, output Payload previous, inout Word count);
        #1ns; previous=payload; mode=value; payload.mode=value; count+=1;
      endtask
    endclass

    task automatic check_published(string name);
      Driver value;
      Driver::Payload packet;
      Driver::Packets packets, returned;
      `SVX_GET_OBJECT(Driver, name, value)
      packet.mode=Driver::ONE; packet.data=12; packets='{packet,packet};
      if(value.echo(Driver::ZERO)!=Driver::ONE) $fatal(1,"enum callback");
      packet=value.echo_payload(packet);
      if(packet.data!==W'(13)) $fatal(1,"struct callback");
      returned=value.echo_packets(packets);
      if(returned[1].data!==W'(14)) $fatal(1,"array callback");
    endtask
  end
endmodule

module tb_generate_runtime_values;
  import svx_pkg::*;
  generate_values #(8) a();
  generate_values #(13) b();
  svx_exports exports();
  initial begin
    svx_init(); exports.initialize();
    svx_load("examples.sv_scoped.generate_runtime_values");
    svx_start("generate_runtime_values.run");
    b.lane[0].check_published("generate_driver");
    if($time!=2) $fatal(1,"task timing");
    svx_shutdown();
    $display("GENERATE_RUNTIME_VALUES_NATIVE_PASS");
    $finish;
  end
endmodule
