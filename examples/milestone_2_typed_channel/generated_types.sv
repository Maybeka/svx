// Generated from examples.milestone_2_typed_channel.tests.typed_test
// Do not edit by hand.

package m2_typed_pkg;

  typedef class M2Transaction;

  class M2Transaction extends svtypes_pkg::sv_object;
    rand bit [15:0] addr;
    rand int data;

    protected bit __svtypes_layered_randomize_active;
    protected int __svtypes_layered_randomize_priority;
    function bit svtypes_layered_randomize_active();
      return __svtypes_layered_randomize_active;
    endfunction
    function int svtypes_layered_randomize_priority();
      return __svtypes_layered_randomize_priority;
    endfunction

    virtual function int layered_randomize();
      int __svtypes_ok;
      bit __svtypes_previous_layered_active;
      int __svtypes_previous_layered_priority;
      int __svtypes_rand_addr;
      int __svtypes_rand_data;
      __svtypes_ok = 1;
      __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
      __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
      __svtypes_layered_randomize_active = 1;
      __svtypes_rand_addr = addr.rand_mode();
      __svtypes_rand_data = data.rand_mode();
      addr.rand_mode(0);
      data.rand_mode(0);
      if (__svtypes_ok) begin
        __svtypes_layered_randomize_priority = 0;
        addr.rand_mode(1);
        data.rand_mode(1);
        if (!this.randomize()) begin
          __svtypes_ok = 0;
        end
        else begin
          addr.rand_mode(0);
          data.rand_mode(0);
        end
      end
      addr.rand_mode(__svtypes_rand_addr);
      data.rand_mode(__svtypes_rand_data);
      __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
      __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
      return __svtypes_ok;
    endfunction

    static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
      svtypes_pkg::encoding_descriptor descriptor;
      descriptor = new("tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 1);
      return descriptor;
    endfunction

    static function svtypes_pkg::runtime_capabilities svtypes_runtime_capabilities();
      return svtypes_pkg::get_runtime_capabilities();
    endfunction

    virtual function void apply_plusargs(string prefix = "");
      string __svtypes_key;
      bit __svtypes_repeated;
      __svtypes_repeated = svtypes_pkg::begin_plusarg_object(__svtypes_object_number);
      if (__svtypes_repeated) begin
        svtypes_pkg::end_plusarg_object();
        return;
      end
      __svtypes_key = (prefix == "") ? "addr=%h" : {prefix, ".addr=%h"};
      if ($test$plusargs((prefix == "") ? "addr" : {prefix, ".addr"}) && !$value$plusargs(__svtypes_key, addr)) $fatal(2, "Malformed plusarg addr");
      __svtypes_key = (prefix == "") ? "data=%d" : {prefix, ".data=%d"};
      if ($test$plusargs((prefix == "") ? "data" : {prefix, ".data"}) && !$value$plusargs(__svtypes_key, data)) $fatal(2, "Malformed plusarg data");
      svtypes_pkg::end_plusarg_object();
    endfunction

    virtual function string svtypes_sprint();
      string result;
      bit repeated;
      repeated = svtypes_pkg::begin_dump_object(__svtypes_object_number);
      if (repeated) begin
        result = $sformatf("<ref#%0d>", __svtypes_object_number);
        svtypes_pkg::end_dump_object();
        return result;
      end
      result = $sformatf("M2Transaction#%0d{", __svtypes_object_number);
      result = {result, "addr="};
      result = {result, $sformatf("%0h", addr)};
      result = {result, ", data="};
      result = {result, $sformatf("%0d", data)};
      result = {result, "}"};
      svtypes_pkg::end_dump_object();
      return result;
    endfunction

    virtual function void svtypes_display();
      $display("%s", svtypes_sprint());
    endfunction

    virtual function void pack(ref byte unsigned bytes[$]);
      svtypes_pkg::begin_pack_graph();
      svtypes_pkg::pack_object_value(this, bytes);
      svtypes_pkg::end_pack_graph();
    endfunction

    virtual function void pack_body(ref byte unsigned bytes[$]);
      ensure_svtypes_object_number();
      svtypes_pkg::register_object(this);
      svtypes_pkg::pack_object_header("tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 2, __svtypes_object_number, bytes);
      svtypes_pkg::bit_packer#(bit [15:0])::pack(addr, bytes);
      svtypes_pkg::int_packer::pack(data, bytes);
    endfunction

    virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
      byte unsigned present;
      svtypes_pkg::require_available(bytes, offset, 1, "object presence");
      present = bytes[offset];
      offset += 1;
      if (present == 8'h02) begin
        $fatal(2, "SvTypes cannot unpack root reference into existing M2Transaction object");
      end
      if (present != 8'h01) begin
        $fatal(2, "SvTypes cannot unpack null into existing M2Transaction object");
      end
      unpack_body(bytes, offset);
    endfunction

    virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
      longint unsigned incoming_svtypes_object_number;
      svtypes_pkg::unpack_object_header("tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 2, incoming_svtypes_object_number, bytes, offset);
      __svtypes_object_number = incoming_svtypes_object_number;
      svtypes_pkg::register_object(this);
      svtypes_pkg::bit_packer#(bit [15:0])::unpack(addr, bytes, offset);
      svtypes_pkg::int_packer::unpack(data, bytes, offset);
    endfunction

    class M2Transaction__svtypes_coverage;
      covergroup cg with function sample(M2Transaction item);
        option.at_least = 1;
        option.auto_bin_max = 64;
        option.comment = "";
        option.cross_num_print_missing = 0;
        option.detect_overlap = 0;
        option.goal = 100;
        option.per_instance = 0;
        option.weight = 1;
        type_option.comment = "";
        type_option.goal = 100;
        type_option.weight = 1;
        addr: coverpoint item.addr {
            option.at_least = 1;
            option.auto_bin_max = 64;
            option.comment = "";
            option.detect_overlap = 0;
            option.goal = 100;
            option.weight = 1;
            bins auto_0_1023_ = {[0:1023]};
            bins auto_10240_11263_ = {[10240:11263]};
            bins auto_1024_2047_ = {[1024:2047]};
            bins auto_11264_12287_ = {[11264:12287]};
            bins auto_12288_13311_ = {[12288:13311]};
            bins auto_13312_14335_ = {[13312:14335]};
            bins auto_14336_15359_ = {[14336:15359]};
            bins auto_15360_16383_ = {[15360:16383]};
            bins auto_16384_17407_ = {[16384:17407]};
            bins auto_17408_18431_ = {[17408:18431]};
            bins auto_18432_19455_ = {[18432:19455]};
            bins auto_19456_20479_ = {[19456:20479]};
            bins auto_20480_21503_ = {[20480:21503]};
            bins auto_2048_3071_ = {[2048:3071]};
            bins auto_21504_22527_ = {[21504:22527]};
            bins auto_22528_23551_ = {[22528:23551]};
            bins auto_23552_24575_ = {[23552:24575]};
            bins auto_24576_25599_ = {[24576:25599]};
            bins auto_25600_26623_ = {[25600:26623]};
            bins auto_26624_27647_ = {[26624:27647]};
            bins auto_27648_28671_ = {[27648:28671]};
            bins auto_28672_29695_ = {[28672:29695]};
            bins auto_29696_30719_ = {[29696:30719]};
            bins auto_30720_31743_ = {[30720:31743]};
            bins auto_3072_4095_ = {[3072:4095]};
            bins auto_31744_32767_ = {[31744:32767]};
            bins auto_32768_33791_ = {[32768:33791]};
            bins auto_33792_34815_ = {[33792:34815]};
            bins auto_34816_35839_ = {[34816:35839]};
            bins auto_35840_36863_ = {[35840:36863]};
            bins auto_36864_37887_ = {[36864:37887]};
            bins auto_37888_38911_ = {[37888:38911]};
            bins auto_38912_39935_ = {[38912:39935]};
            bins auto_39936_40959_ = {[39936:40959]};
            bins auto_40960_41983_ = {[40960:41983]};
            bins auto_4096_5119_ = {[4096:5119]};
            bins auto_41984_43007_ = {[41984:43007]};
            bins auto_43008_44031_ = {[43008:44031]};
            bins auto_44032_45055_ = {[44032:45055]};
            bins auto_45056_46079_ = {[45056:46079]};
            bins auto_46080_47103_ = {[46080:47103]};
            bins auto_47104_48127_ = {[47104:48127]};
            bins auto_48128_49151_ = {[48128:49151]};
            bins auto_49152_50175_ = {[49152:50175]};
            bins auto_50176_51199_ = {[50176:51199]};
            bins auto_51200_52223_ = {[51200:52223]};
            bins auto_5120_6143_ = {[5120:6143]};
            bins auto_52224_53247_ = {[52224:53247]};
            bins auto_53248_54271_ = {[53248:54271]};
            bins auto_54272_55295_ = {[54272:55295]};
            bins auto_55296_56319_ = {[55296:56319]};
            bins auto_56320_57343_ = {[56320:57343]};
            bins auto_57344_58367_ = {[57344:58367]};
            bins auto_58368_59391_ = {[58368:59391]};
            bins auto_59392_60415_ = {[59392:60415]};
            bins auto_60416_61439_ = {[60416:61439]};
            bins auto_61440_62463_ = {[61440:62463]};
            bins auto_6144_7167_ = {[6144:7167]};
            bins auto_62464_63487_ = {[62464:63487]};
            bins auto_63488_64511_ = {[63488:64511]};
            bins auto_64512_65535_ = {[64512:65535]};
            bins auto_7168_8191_ = {[7168:8191]};
            bins auto_8192_9215_ = {[8192:9215]};
            bins auto_9216_10239_ = {[9216:10239]};
        }
        data: coverpoint item.data {
            option.at_least = 1;
            option.auto_bin_max = 64;
            option.comment = "";
            option.detect_overlap = 0;
            option.goal = 100;
            option.weight = 1;
            bins auto__1006632960__939524097_ = {[-1006632960:-939524097]};
            bins auto__1073741824__1006632961_ = {[-1073741824:-1006632961]};
            bins auto__1140850688__1073741825_ = {[-1140850688:-1073741825]};
            bins auto__1207959552__1140850689_ = {[-1207959552:-1140850689]};
            bins auto__1275068416__1207959553_ = {[-1275068416:-1207959553]};
            bins auto__1342177280__1275068417_ = {[-1342177280:-1275068417]};
            bins auto__134217728__67108865_ = {[-134217728:-67108865]};
            bins auto__1409286144__1342177281_ = {[-1409286144:-1342177281]};
            bins auto__1476395008__1409286145_ = {[-1476395008:-1409286145]};
            bins auto__1543503872__1476395009_ = {[-1543503872:-1476395009]};
            bins auto__1610612736__1543503873_ = {[-1610612736:-1543503873]};
            bins auto__1677721600__1610612737_ = {[-1677721600:-1610612737]};
            bins auto__1744830464__1677721601_ = {[-1744830464:-1677721601]};
            bins auto__1811939328__1744830465_ = {[-1811939328:-1744830465]};
            bins auto__1879048192__1811939329_ = {[-1879048192:-1811939329]};
            bins auto__1946157056__1879048193_ = {[-1946157056:-1879048193]};
            bins auto__2013265920__1946157057_ = {[-2013265920:-1946157057]};
            bins auto__201326592__134217729_ = {[-201326592:-134217729]};
            bins auto__2080374784__2013265921_ = {[-2080374784:-2013265921]};
            bins auto__2147483648__2080374785_ = {[-2147483648:-2080374785]};
            bins auto__268435456__201326593_ = {[-268435456:-201326593]};
            bins auto__335544320__268435457_ = {[-335544320:-268435457]};
            bins auto__402653184__335544321_ = {[-402653184:-335544321]};
            bins auto__469762048__402653185_ = {[-469762048:-402653185]};
            bins auto__536870912__469762049_ = {[-536870912:-469762049]};
            bins auto__603979776__536870913_ = {[-603979776:-536870913]};
            bins auto__671088640__603979777_ = {[-671088640:-603979777]};
            bins auto__67108864__1_ = {[-67108864:-1]};
            bins auto__738197504__671088641_ = {[-738197504:-671088641]};
            bins auto__805306368__738197505_ = {[-805306368:-738197505]};
            bins auto__872415232__805306369_ = {[-872415232:-805306369]};
            bins auto__939524096__872415233_ = {[-939524096:-872415233]};
            bins auto_0_67108863_ = {[0:67108863]};
            bins auto_1006632960_1073741823_ = {[1006632960:1073741823]};
            bins auto_1073741824_1140850687_ = {[1073741824:1140850687]};
            bins auto_1140850688_1207959551_ = {[1140850688:1207959551]};
            bins auto_1207959552_1275068415_ = {[1207959552:1275068415]};
            bins auto_1275068416_1342177279_ = {[1275068416:1342177279]};
            bins auto_1342177280_1409286143_ = {[1342177280:1409286143]};
            bins auto_134217728_201326591_ = {[134217728:201326591]};
            bins auto_1409286144_1476395007_ = {[1409286144:1476395007]};
            bins auto_1476395008_1543503871_ = {[1476395008:1543503871]};
            bins auto_1543503872_1610612735_ = {[1543503872:1610612735]};
            bins auto_1610612736_1677721599_ = {[1610612736:1677721599]};
            bins auto_1677721600_1744830463_ = {[1677721600:1744830463]};
            bins auto_1744830464_1811939327_ = {[1744830464:1811939327]};
            bins auto_1811939328_1879048191_ = {[1811939328:1879048191]};
            bins auto_1879048192_1946157055_ = {[1879048192:1946157055]};
            bins auto_1946157056_2013265919_ = {[1946157056:2013265919]};
            bins auto_2013265920_2080374783_ = {[2013265920:2080374783]};
            bins auto_201326592_268435455_ = {[201326592:268435455]};
            bins auto_2080374784_2147483647_ = {[2080374784:2147483647]};
            bins auto_268435456_335544319_ = {[268435456:335544319]};
            bins auto_335544320_402653183_ = {[335544320:402653183]};
            bins auto_402653184_469762047_ = {[402653184:469762047]};
            bins auto_469762048_536870911_ = {[469762048:536870911]};
            bins auto_536870912_603979775_ = {[536870912:603979775]};
            bins auto_603979776_671088639_ = {[603979776:671088639]};
            bins auto_671088640_738197503_ = {[671088640:738197503]};
            bins auto_67108864_134217727_ = {[67108864:134217727]};
            bins auto_738197504_805306367_ = {[738197504:805306367]};
            bins auto_805306368_872415231_ = {[805306368:872415231]};
            bins auto_872415232_939524095_ = {[872415232:939524095]};
            bins auto_939524096_1006632959_ = {[939524096:1006632959]};
        }
      endgroup

      function new();
        cg = new();
      endfunction

      function void sample(M2Transaction item);
        cg.sample(item);
      endfunction

      function real get_coverage();
        return cg.get_coverage();
      endfunction
    endclass
  endclass

  // SvTypes typed channel helpers
  task automatic svx_get_M2Transaction(string channel_name, output M2Transaction item);
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    svx_pkg::svx_channel_get_payload(channel_name, payload);
    svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M2Transaction", "tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 1, "svx_get_M2Transaction", bytes);
    svx_pkg::svx_payload_destroy(payload);
    item = new();
    offset = 0;
    item.unpack(bytes, offset);
    svx_pkg::svx_require_unpacked_all("svx_get_M2Transaction", channel_name, "M2Transaction", offset, bytes.size());
  endtask

  task automatic svx_peek_M2Transaction(string channel_name, output M2Transaction item);
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    svx_pkg::svx_channel_peek_payload(channel_name, payload);
    svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M2Transaction", "tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 1, "svx_peek_M2Transaction", bytes);
    item = new();
    offset = 0;
    item.unpack(bytes, offset);
    svx_pkg::svx_require_unpacked_all("svx_peek_M2Transaction", channel_name, "M2Transaction", offset, bytes.size());
  endtask

  task automatic svx_put_M2Transaction(string channel_name, input M2Transaction item);
    byte unsigned bytes[$];
    if (item == null) begin
      $fatal(2, "svx_put_M2Transaction(%s): cannot put null SvTypes object type M2Transaction", channel_name);
    end
    item.pack(bytes);
    svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M2Transaction", "application/x-svtypes", "tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 1);
  endtask

  task automatic svx_try_get_M2Transaction(string channel_name, output bit ok, output M2Transaction item);
    chandle payload;
    byte unsigned bytes[$];
    int offset;
    payload = svx_pkg::svx_channel_try_get_payload(channel_name);
    if (payload == null) begin
      ok = 0;
      item = null;
      return;
    end
    svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M2Transaction", "tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 1, "svx_try_get_M2Transaction", bytes);
    svx_pkg::svx_payload_destroy(payload);
    item = new();
    offset = 0;
    item.unpack(bytes, offset);
    svx_pkg::svx_require_unpacked_all("svx_try_get_M2Transaction", channel_name, "M2Transaction", offset, bytes.size());
    ok = 1;
  endtask

  function automatic bit svx_try_put_M2Transaction(string channel_name, input M2Transaction item);
    byte unsigned bytes[$];
    if (item == null) begin
      $fatal(2, "svx_try_put_M2Transaction(%s): cannot put null SvTypes object type M2Transaction", channel_name);
    end
    item.pack(bytes);
    return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M2Transaction", "application/x-svtypes", "tests.M2Transaction", "078e2d155485aaca5a4356700b4729c0195af29e2c81847515d14ab1016ca034", 1);
  endfunction

endpackage : m2_typed_pkg
