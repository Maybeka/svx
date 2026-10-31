// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`include "sv/svx_defs.svh"

module runtime_values #(int W=8);
  import svx_pkg::*;
  typedef enum bit[W-1:0] {ZERO=W'(0), ONE=W'(1)} Mode;
  typedef struct packed {Mode mode; bit[W-1:0] data;} Payload;
  typedef bit[W-1:0] Word;
  typedef Payload Packets[2];
  typedef Mode Modes[$];

  class Driver;
    Mode mode;
    Payload payload;
    function new(Mode initial_mode); mode=initial_mode; endfunction
    virtual function Mode echo(input Mode value); mode=value; return mode; endfunction
    virtual function Payload echo_payload(input Payload value); payload=value; return payload; endfunction
    function Modes echo_modes(input Modes values); return values; endfunction
    virtual function Packets echo_packets(input Packets values); return values; endfunction
    task advance(input Mode value, output Payload previous, inout Word count);
      #1ns; previous=payload; mode=value; payload.mode=value; count+=1;
    endtask
    static function Mode static_echo(Mode value); return value; endfunction
  endclass

  task automatic check_published(string name);
    Driver value;
    Payload packet;
    Packets packets,returned;
    `SVX_GET_OBJECT(Driver,name,value)
    packet.mode=ONE; packet.data=12; packets='{packet,packet};
    if(value.echo(ZERO)!=ONE) $fatal(1,"enum callback");
    packet=value.echo_payload(packet);
    if(packet.data!=13) $fatal(1,"struct callback");
    returned=value.echo_packets(packets);
    if(returned[1].data!=14) $fatal(1,"array callback");
  endtask
endmodule

module tb_instance_runtime_values;
  import svx_pkg::*;
  runtime_values a(),b();
  runtime_values #(13) c();
  svx_exports exports();
  initial begin
    svx_init();
    exports.initialize();
    svx_load("examples.sv_scoped.instance_runtime_values");
    svx_start("instance_runtime_values.run");
    b.check_published("b");
    if($time!=3) $fatal(1,"task timing");
    svx_shutdown();
    $display("INSTANCE_RUNTIME_VALUES_NATIVE_PASS");
    $finish;
  end
endmodule
