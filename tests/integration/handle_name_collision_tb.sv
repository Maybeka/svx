`timescale 1ns/1ps
`include "sv/svx_defs.svh"

module handle_name_collision_tb;
  import svx_pkg::*;
  import collision_api::*;

  initial begin
    Owner owner;
    a_b::C left, returned_left;
    a::b_C right, returned_right;
    svx_init();
    svx_exports_pkg::initialize();
    svx_load("tests.integration.handle_name_collision");
    svx_start("handle_collision.run");
    `SVX_GET_OBJECT(Owner, "handle_collision.instance", owner)
    left = new(31);
    right = new(47);
    returned_left = owner.echo_left(left);
    returned_right = owner.echo_right(right);
    if (returned_left != left || returned_right != right)
      $fatal(1, "different native handle types lost their identity");
    svx_start("handle_collision.verify");
    svx_shutdown();
    $display("HANDLE_NAME_COLLISION_NATIVE_PASS");
    $finish;
  end
endmodule
