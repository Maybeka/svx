// SPDX-License-Identifier: Apache-2.0
module struct_kinds_codec_tb;
  import struct_kinds_pkg::*;
  import svx_call_records_pkg::*;
  initial begin
    Item original=new();
    Handles value, restored;
    byte unsigned bytes[$];
    int offset=0;
    value.item=original;
    value.same_item=original;
    value.fixed_items='{original, null};
    value.dynamic_items=new[2];
    value.dynamic_items[0]=original;
    value.dynamic_items[1]=null;
    value.queue_items='{original, null, original};
    value.by_key["shared"]=original;
    value.by_key["empty"]=null;
    SVXValue_16_struct_kinds_pkg_Handles_packer::pack(value, bytes);
    SVXValue_16_struct_kinds_pkg_Handles_packer::unpack(restored, bytes, offset);
    if (offset != bytes.size()) $fatal(1, "codec did not consume all bytes");
    if (restored.item != original || restored.same_item != original) $fatal(1, "direct identity");
    if (restored.fixed_items[0] != original || restored.fixed_items[1] != null) $fatal(1, "fixed identity");
    if (restored.dynamic_items.size() != 2 || restored.dynamic_items[0] != original ||
        restored.dynamic_items[1] != null) $fatal(1, "dynamic identity");
    if (restored.queue_items.size() != 3 || restored.queue_items[0] != original ||
        restored.queue_items[1] != null || restored.queue_items[2] != original) $fatal(1, "queue identity");
    if (restored.by_key.num() != 2 || restored.by_key["shared"] != original ||
        restored.by_key["empty"] != null) $fatal(1, "associative identity");
    restored.item.code=29;
    if (value.same_item.code != 29) $fatal(1, "referent cloned");
    $display("STRUCT_KINDS_NATIVE_CODEC_PASS");
    $finish;
  end
endmodule
