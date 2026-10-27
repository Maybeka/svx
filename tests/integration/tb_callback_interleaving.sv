`include "svtypes_pkg.sv"
`include "tests/integration/callback_interleaving.sv"
`include "sv/svx_pkg.sv"
`include ".tmp/callback_interleaving/mirrors.sv"
module tb;
  import svx_pkg::*;
  initial begin
    callback_interleaving_pkg::Base item;
    svx_pkg::svx_init();
    svx_pkg::svx_load("tests.integration.callback_interleaving_test");
    svx_pkg::svx_start("callback_interleaving.create");
    `SVX_GET_OBJECT(callback_interleaving_pkg::Base, "callback_interleaving.item", item)
    fork
      item.work(1);
      begin #1ns; item.work(2); end
    join
    svx_pkg::svx_start("callback_interleaving.verify");
    svx_pkg::svx_shutdown();
    $display("CALLBACK_INTERLEAVING_SV_PASS");
    $finish;
  end
endmodule
