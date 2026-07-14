`include "sv/svx_pkg.sv"

module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import svx_pkg::*;

  initial begin
    chandle payload;
    string kind;
    string type_name;
    string content_type;
    byte unsigned sv_data[] = '{8'hde, 8'had, 8'hbe, 8'hef, 8'h00, 8'h11, 8'h22};
    byte unsigned expected_try_put[] = '{"t", "r", "y", "-", "p", "u", "t", "-", "o", "k"};

    $display("M2 payload test start @ %0.3f ns", $realtime);

    svx_init();
    svx_load("examples.milestone_2_payload_channel.tests.payload_test");

    svx_start("examples.milestone_2_payload_channel.tests.payload_test.python_puts_payload");

    svx_channel_peek_payload("m2.py_to_sv", payload);
    if (svx_payload_size(payload) != 6) begin
      $fatal(2, "unexpected peek Python->SV size: %0d", svx_payload_size(payload));
    end
    if (svx_payload_get_byte(payload, 0) != 8'h00 ||
        svx_payload_get_byte(payload, 1) != 8'h01 ||
        svx_payload_get_byte(payload, 2) != 8'h02 ||
        svx_payload_get_byte(payload, 3) != 8'h7f ||
        svx_payload_get_byte(payload, 4) != 8'h80 ||
        svx_payload_get_byte(payload, 5) != 8'hff) begin
      $fatal(2, "unexpected peek Python->SV bytes");
    end

    svx_channel_get_payload("m2.py_to_sv", payload);
    kind = svx_payload_kind(payload);
    type_name = svx_payload_type_name(payload);
    content_type = svx_payload_content_type(payload);

    $display(
      "SV received from Python kind=%s type=%s content=%s size=%0d",
      kind, type_name, content_type, svx_payload_size(payload)
    );

    if (kind != "bytes") $fatal(2, "unexpected kind: %s", kind);
    if (content_type != "application/octet-stream") begin
      $fatal(2, "unexpected content_type: %s", content_type);
    end
    if (svx_payload_size(payload) != 6 ||
        svx_payload_get_byte(payload, 0) != 8'h00 ||
        svx_payload_get_byte(payload, 5) != 8'hff) begin
      $fatal(2, "unexpected Python->SV binary data");
    end
    svx_payload_destroy(payload);

    payload = svx_channel_try_get_payload("m2.py_to_sv");
    if (payload != null) begin
      $fatal(2, "try_get should have returned empty after consuming m2.py_to_sv");
    end

    svx_channel_get_payload("m2.py_try_put_to_sv", payload);
    kind = svx_payload_kind(payload);
    type_name = svx_payload_type_name(payload);
    content_type = svx_payload_content_type(payload);
    if (kind != "trace") $fatal(2, "unexpected try_put kind: %s", kind);
    if (type_name != "ascii") $fatal(2, "unexpected try_put type: %s", type_name);
    if (content_type != "text/plain") begin
      $fatal(2, "unexpected try_put content_type: %s", content_type);
    end
    if (svx_payload_size(payload) != expected_try_put.size()) begin
      $fatal(2, "unexpected try_put size: %0d", svx_payload_size(payload));
    end
    foreach (expected_try_put[i]) begin
      if (svx_payload_get_byte(payload, i) != expected_try_put[i]) begin
        $fatal(2, "unexpected try_put byte[%0d]", i);
      end
    end
    svx_payload_destroy(payload);

    fork
      begin
        svx_start("examples.milestone_2_payload_channel.tests.payload_test.python_gets_payload");
      end
      begin
        #(1.25ns);
        svx_channel_put_bytes(
          "m2.sv_to_py",
          sv_data,
          "trace",
          "raw.bytes",
          "application/octet-stream"
        );
      end
    join

    svx_start("examples.milestone_2_payload_channel.tests.payload_test.python_puts_large_payload");
    svx_channel_get_payload("m2.large_py_to_sv", payload);
    kind = svx_payload_kind(payload);
    type_name = svx_payload_type_name(payload);
    content_type = svx_payload_content_type(payload);
    if (kind != "bytes") $fatal(2, "unexpected large kind: %s", kind);
    if (type_name != "large.pattern") $fatal(2, "unexpected large type: %s", type_name);
    if (svx_payload_size(payload) != 1024 * 1024) begin
      $fatal(2, "unexpected large size: %0d", svx_payload_size(payload));
    end
    if (svx_payload_get_byte(payload, 0) != 8'h00 ||
        svx_payload_get_byte(payload, 1) != 8'h01 ||
        svx_payload_get_byte(payload, 2) != 8'h02 ||
        svx_payload_get_byte(payload, 3) != 8'h03) begin
      $fatal(2, "unexpected large prefix");
    end
    if (svx_payload_get_byte(payload, 1024 * 1024 - 4) != 8'hfc ||
        svx_payload_get_byte(payload, 1024 * 1024 - 3) != 8'hfd ||
        svx_payload_get_byte(payload, 1024 * 1024 - 2) != 8'hfe ||
        svx_payload_get_byte(payload, 1024 * 1024 - 1) != 8'hff) begin
      $fatal(2, "unexpected large suffix");
    end
    $display("SV received large payload size=%0d", svx_payload_size(payload));
    svx_payload_destroy(payload);

    $display("M2 payload test done @ %0.3f ns", $realtime);
    $finish;
  end
endmodule
