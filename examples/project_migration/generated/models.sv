// Generated from examples.project_migration.models
// Do not edit by hand.

typedef class MigrationRequest;
typedef class MigrationResponse;
typedef class MigrationObservation;

class MigrationRequest extends svtypes_pkg::sv_object;
  rand int tag;
  rand bit [0:0] stop;
  rand bit [0:0] write;
  rand bit [7:0] address;
  rand bit [31:0] data;

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
    int __svtypes_rand_tag;
    int __svtypes_rand_stop;
    int __svtypes_rand_write;
    int __svtypes_rand_address;
    int __svtypes_rand_data;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_tag = tag.rand_mode();
    __svtypes_rand_stop = stop.rand_mode();
    __svtypes_rand_write = write.rand_mode();
    __svtypes_rand_address = address.rand_mode();
    __svtypes_rand_data = data.rand_mode();
    tag.rand_mode(0);
    stop.rand_mode(0);
    write.rand_mode(0);
    address.rand_mode(0);
    data.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      tag.rand_mode(1);
      stop.rand_mode(1);
      write.rand_mode(1);
      address.rand_mode(1);
      data.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        tag.rand_mode(0);
        stop.rand_mode(0);
        write.rand_mode(0);
        address.rand_mode(0);
        data.rand_mode(0);
      end
    end
    tag.rand_mode(__svtypes_rand_tag);
    stop.rand_mode(__svtypes_rand_stop);
    write.rand_mode(__svtypes_rand_write);
    address.rand_mode(__svtypes_rand_address);
    data.rand_mode(__svtypes_rand_data);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1);
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
    __svtypes_key = (prefix == "") ? "tag=%d" : {prefix, ".tag=%d"};
    if ($test$plusargs((prefix == "") ? "tag" : {prefix, ".tag"}) && !$value$plusargs(__svtypes_key, tag)) $fatal(2, "Malformed plusarg tag");
    __svtypes_key = (prefix == "") ? "stop=%h" : {prefix, ".stop=%h"};
    if ($test$plusargs((prefix == "") ? "stop" : {prefix, ".stop"}) && !$value$plusargs(__svtypes_key, stop)) $fatal(2, "Malformed plusarg stop");
    __svtypes_key = (prefix == "") ? "write=%h" : {prefix, ".write=%h"};
    if ($test$plusargs((prefix == "") ? "write" : {prefix, ".write"}) && !$value$plusargs(__svtypes_key, write)) $fatal(2, "Malformed plusarg write");
    __svtypes_key = (prefix == "") ? "address=%h" : {prefix, ".address=%h"};
    if ($test$plusargs((prefix == "") ? "address" : {prefix, ".address"}) && !$value$plusargs(__svtypes_key, address)) $fatal(2, "Malformed plusarg address");
    __svtypes_key = (prefix == "") ? "data=%h" : {prefix, ".data=%h"};
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
    result = $sformatf("MigrationRequest#%0d{", __svtypes_object_number);
    result = {result, "tag="};
    result = {result, $sformatf("%0d", this.tag)};
    result = {result, ", stop="};
    result = {result, $sformatf("%0h", this.stop)};
    result = {result, ", write="};
    result = {result, $sformatf("%0h", this.write)};
    result = {result, ", address="};
    result = {result, $sformatf("%0h", this.address)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", this.data)};
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
    svtypes_pkg::pack_object_header("project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 5, __svtypes_object_number, bytes);
    svtypes_pkg::int_packer::pack(tag, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(stop, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(write, bytes);
    svtypes_pkg::bit_packer#(bit [7:0])::pack(address, bytes);
    svtypes_pkg::bit_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing MigrationRequest object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing MigrationRequest object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 5, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(tag, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(stop, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(write, bytes, offset);
    svtypes_pkg::bit_packer#(bit [7:0])::unpack(address, bytes, offset);
    svtypes_pkg::bit_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction

  class MigrationRequest__svtypes_coverage;
    covergroup cg with function sample(MigrationRequest item);
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
      address: coverpoint item.address {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_3_ = {[0:3]};
          bins auto_100_103_ = {[100:103]};
          bins auto_104_107_ = {[104:107]};
          bins auto_108_111_ = {[108:111]};
          bins auto_112_115_ = {[112:115]};
          bins auto_116_119_ = {[116:119]};
          bins auto_120_123_ = {[120:123]};
          bins auto_124_127_ = {[124:127]};
          bins auto_128_131_ = {[128:131]};
          bins auto_12_15_ = {[12:15]};
          bins auto_132_135_ = {[132:135]};
          bins auto_136_139_ = {[136:139]};
          bins auto_140_143_ = {[140:143]};
          bins auto_144_147_ = {[144:147]};
          bins auto_148_151_ = {[148:151]};
          bins auto_152_155_ = {[152:155]};
          bins auto_156_159_ = {[156:159]};
          bins auto_160_163_ = {[160:163]};
          bins auto_164_167_ = {[164:167]};
          bins auto_168_171_ = {[168:171]};
          bins auto_16_19_ = {[16:19]};
          bins auto_172_175_ = {[172:175]};
          bins auto_176_179_ = {[176:179]};
          bins auto_180_183_ = {[180:183]};
          bins auto_184_187_ = {[184:187]};
          bins auto_188_191_ = {[188:191]};
          bins auto_192_195_ = {[192:195]};
          bins auto_196_199_ = {[196:199]};
          bins auto_200_203_ = {[200:203]};
          bins auto_204_207_ = {[204:207]};
          bins auto_208_211_ = {[208:211]};
          bins auto_20_23_ = {[20:23]};
          bins auto_212_215_ = {[212:215]};
          bins auto_216_219_ = {[216:219]};
          bins auto_220_223_ = {[220:223]};
          bins auto_224_227_ = {[224:227]};
          bins auto_228_231_ = {[228:231]};
          bins auto_232_235_ = {[232:235]};
          bins auto_236_239_ = {[236:239]};
          bins auto_240_243_ = {[240:243]};
          bins auto_244_247_ = {[244:247]};
          bins auto_248_251_ = {[248:251]};
          bins auto_24_27_ = {[24:27]};
          bins auto_252_255_ = {[252:255]};
          bins auto_28_31_ = {[28:31]};
          bins auto_32_35_ = {[32:35]};
          bins auto_36_39_ = {[36:39]};
          bins auto_40_43_ = {[40:43]};
          bins auto_44_47_ = {[44:47]};
          bins auto_48_51_ = {[48:51]};
          bins auto_4_7_ = {[4:7]};
          bins auto_52_55_ = {[52:55]};
          bins auto_56_59_ = {[56:59]};
          bins auto_60_63_ = {[60:63]};
          bins auto_64_67_ = {[64:67]};
          bins auto_68_71_ = {[68:71]};
          bins auto_72_75_ = {[72:75]};
          bins auto_76_79_ = {[76:79]};
          bins auto_80_83_ = {[80:83]};
          bins auto_84_87_ = {[84:87]};
          bins auto_88_91_ = {[88:91]};
          bins auto_8_11_ = {[8:11]};
          bins auto_92_95_ = {[92:95]};
          bins auto_96_99_ = {[96:99]};
      }
      data: coverpoint item.data {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
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
          bins auto_2147483648_2214592511_ = {[32'h80000000:32'h83ffffff]};
          bins auto_2214592512_2281701375_ = {[32'h84000000:32'h87ffffff]};
          bins auto_2281701376_2348810239_ = {[32'h88000000:32'h8bffffff]};
          bins auto_2348810240_2415919103_ = {[32'h8c000000:32'h8fffffff]};
          bins auto_2415919104_2483027967_ = {[32'h90000000:32'h93ffffff]};
          bins auto_2483027968_2550136831_ = {[32'h94000000:32'h97ffffff]};
          bins auto_2550136832_2617245695_ = {[32'h98000000:32'h9bffffff]};
          bins auto_2617245696_2684354559_ = {[32'h9c000000:32'h9fffffff]};
          bins auto_2684354560_2751463423_ = {[32'ha0000000:32'ha3ffffff]};
          bins auto_268435456_335544319_ = {[268435456:335544319]};
          bins auto_2751463424_2818572287_ = {[32'ha4000000:32'ha7ffffff]};
          bins auto_2818572288_2885681151_ = {[32'ha8000000:32'habffffff]};
          bins auto_2885681152_2952790015_ = {[32'hac000000:32'hafffffff]};
          bins auto_2952790016_3019898879_ = {[32'hb0000000:32'hb3ffffff]};
          bins auto_3019898880_3087007743_ = {[32'hb4000000:32'hb7ffffff]};
          bins auto_3087007744_3154116607_ = {[32'hb8000000:32'hbbffffff]};
          bins auto_3154116608_3221225471_ = {[32'hbc000000:32'hbfffffff]};
          bins auto_3221225472_3288334335_ = {[32'hc0000000:32'hc3ffffff]};
          bins auto_3288334336_3355443199_ = {[32'hc4000000:32'hc7ffffff]};
          bins auto_3355443200_3422552063_ = {[32'hc8000000:32'hcbffffff]};
          bins auto_335544320_402653183_ = {[335544320:402653183]};
          bins auto_3422552064_3489660927_ = {[32'hcc000000:32'hcfffffff]};
          bins auto_3489660928_3556769791_ = {[32'hd0000000:32'hd3ffffff]};
          bins auto_3556769792_3623878655_ = {[32'hd4000000:32'hd7ffffff]};
          bins auto_3623878656_3690987519_ = {[32'hd8000000:32'hdbffffff]};
          bins auto_3690987520_3758096383_ = {[32'hdc000000:32'hdfffffff]};
          bins auto_3758096384_3825205247_ = {[32'he0000000:32'he3ffffff]};
          bins auto_3825205248_3892314111_ = {[32'he4000000:32'he7ffffff]};
          bins auto_3892314112_3959422975_ = {[32'he8000000:32'hebffffff]};
          bins auto_3959422976_4026531839_ = {[32'hec000000:32'hefffffff]};
          bins auto_4026531840_4093640703_ = {[32'hf0000000:32'hf3ffffff]};
          bins auto_402653184_469762047_ = {[402653184:469762047]};
          bins auto_4093640704_4160749567_ = {[32'hf4000000:32'hf7ffffff]};
          bins auto_4160749568_4227858431_ = {[32'hf8000000:32'hfbffffff]};
          bins auto_4227858432_4294967295_ = {[32'hfc000000:32'hffffffff]};
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
      stop: coverpoint item.stop {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_ = {0};
          bins auto_1_ = {1};
      }
      tag: coverpoint item.tag {
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
      write: coverpoint item.write {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_ = {0};
          bins auto_1_ = {1};
      }
    endgroup

    function new();
      cg = new();
    endfunction

    function void sample(MigrationRequest item);
      cg.sample(item);
    endfunction

    function real get_coverage();
      return cg.get_coverage();
    endfunction
  endclass
endclass

class MigrationResponse extends svtypes_pkg::sv_object;
  rand int tag;
  rand bit [0:0] stop;
  rand bit [31:0] data;

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
    int __svtypes_rand_tag;
    int __svtypes_rand_stop;
    int __svtypes_rand_data;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_tag = tag.rand_mode();
    __svtypes_rand_stop = stop.rand_mode();
    __svtypes_rand_data = data.rand_mode();
    tag.rand_mode(0);
    stop.rand_mode(0);
    data.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      tag.rand_mode(1);
      stop.rand_mode(1);
      data.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        tag.rand_mode(0);
        stop.rand_mode(0);
        data.rand_mode(0);
      end
    end
    tag.rand_mode(__svtypes_rand_tag);
    stop.rand_mode(__svtypes_rand_stop);
    data.rand_mode(__svtypes_rand_data);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1);
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
    __svtypes_key = (prefix == "") ? "tag=%d" : {prefix, ".tag=%d"};
    if ($test$plusargs((prefix == "") ? "tag" : {prefix, ".tag"}) && !$value$plusargs(__svtypes_key, tag)) $fatal(2, "Malformed plusarg tag");
    __svtypes_key = (prefix == "") ? "stop=%h" : {prefix, ".stop=%h"};
    if ($test$plusargs((prefix == "") ? "stop" : {prefix, ".stop"}) && !$value$plusargs(__svtypes_key, stop)) $fatal(2, "Malformed plusarg stop");
    __svtypes_key = (prefix == "") ? "data=%h" : {prefix, ".data=%h"};
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
    result = $sformatf("MigrationResponse#%0d{", __svtypes_object_number);
    result = {result, "tag="};
    result = {result, $sformatf("%0d", this.tag)};
    result = {result, ", stop="};
    result = {result, $sformatf("%0h", this.stop)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", this.data)};
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
    svtypes_pkg::pack_object_header("project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 3, __svtypes_object_number, bytes);
    svtypes_pkg::int_packer::pack(tag, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(stop, bytes);
    svtypes_pkg::bit_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing MigrationResponse object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing MigrationResponse object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 3, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(tag, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(stop, bytes, offset);
    svtypes_pkg::bit_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction

  class MigrationResponse__svtypes_coverage;
    covergroup cg with function sample(MigrationResponse item);
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
      data: coverpoint item.data {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
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
          bins auto_2147483648_2214592511_ = {[32'h80000000:32'h83ffffff]};
          bins auto_2214592512_2281701375_ = {[32'h84000000:32'h87ffffff]};
          bins auto_2281701376_2348810239_ = {[32'h88000000:32'h8bffffff]};
          bins auto_2348810240_2415919103_ = {[32'h8c000000:32'h8fffffff]};
          bins auto_2415919104_2483027967_ = {[32'h90000000:32'h93ffffff]};
          bins auto_2483027968_2550136831_ = {[32'h94000000:32'h97ffffff]};
          bins auto_2550136832_2617245695_ = {[32'h98000000:32'h9bffffff]};
          bins auto_2617245696_2684354559_ = {[32'h9c000000:32'h9fffffff]};
          bins auto_2684354560_2751463423_ = {[32'ha0000000:32'ha3ffffff]};
          bins auto_268435456_335544319_ = {[268435456:335544319]};
          bins auto_2751463424_2818572287_ = {[32'ha4000000:32'ha7ffffff]};
          bins auto_2818572288_2885681151_ = {[32'ha8000000:32'habffffff]};
          bins auto_2885681152_2952790015_ = {[32'hac000000:32'hafffffff]};
          bins auto_2952790016_3019898879_ = {[32'hb0000000:32'hb3ffffff]};
          bins auto_3019898880_3087007743_ = {[32'hb4000000:32'hb7ffffff]};
          bins auto_3087007744_3154116607_ = {[32'hb8000000:32'hbbffffff]};
          bins auto_3154116608_3221225471_ = {[32'hbc000000:32'hbfffffff]};
          bins auto_3221225472_3288334335_ = {[32'hc0000000:32'hc3ffffff]};
          bins auto_3288334336_3355443199_ = {[32'hc4000000:32'hc7ffffff]};
          bins auto_3355443200_3422552063_ = {[32'hc8000000:32'hcbffffff]};
          bins auto_335544320_402653183_ = {[335544320:402653183]};
          bins auto_3422552064_3489660927_ = {[32'hcc000000:32'hcfffffff]};
          bins auto_3489660928_3556769791_ = {[32'hd0000000:32'hd3ffffff]};
          bins auto_3556769792_3623878655_ = {[32'hd4000000:32'hd7ffffff]};
          bins auto_3623878656_3690987519_ = {[32'hd8000000:32'hdbffffff]};
          bins auto_3690987520_3758096383_ = {[32'hdc000000:32'hdfffffff]};
          bins auto_3758096384_3825205247_ = {[32'he0000000:32'he3ffffff]};
          bins auto_3825205248_3892314111_ = {[32'he4000000:32'he7ffffff]};
          bins auto_3892314112_3959422975_ = {[32'he8000000:32'hebffffff]};
          bins auto_3959422976_4026531839_ = {[32'hec000000:32'hefffffff]};
          bins auto_4026531840_4093640703_ = {[32'hf0000000:32'hf3ffffff]};
          bins auto_402653184_469762047_ = {[402653184:469762047]};
          bins auto_4093640704_4160749567_ = {[32'hf4000000:32'hf7ffffff]};
          bins auto_4160749568_4227858431_ = {[32'hf8000000:32'hfbffffff]};
          bins auto_4227858432_4294967295_ = {[32'hfc000000:32'hffffffff]};
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
      stop: coverpoint item.stop {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_ = {0};
          bins auto_1_ = {1};
      }
      tag: coverpoint item.tag {
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

    function void sample(MigrationResponse item);
      cg.sample(item);
    endfunction

    function real get_coverage();
      return cg.get_coverage();
    endfunction
  endclass
endclass

class MigrationObservation extends svtypes_pkg::sv_object;
  rand int tag;
  rand bit [0:0] stop;
  rand bit [0:0] write;
  rand bit [7:0] address;
  rand bit [31:0] data;

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
    int __svtypes_rand_tag;
    int __svtypes_rand_stop;
    int __svtypes_rand_write;
    int __svtypes_rand_address;
    int __svtypes_rand_data;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_tag = tag.rand_mode();
    __svtypes_rand_stop = stop.rand_mode();
    __svtypes_rand_write = write.rand_mode();
    __svtypes_rand_address = address.rand_mode();
    __svtypes_rand_data = data.rand_mode();
    tag.rand_mode(0);
    stop.rand_mode(0);
    write.rand_mode(0);
    address.rand_mode(0);
    data.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      tag.rand_mode(1);
      stop.rand_mode(1);
      write.rand_mode(1);
      address.rand_mode(1);
      data.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        tag.rand_mode(0);
        stop.rand_mode(0);
        write.rand_mode(0);
        address.rand_mode(0);
        data.rand_mode(0);
      end
    end
    tag.rand_mode(__svtypes_rand_tag);
    stop.rand_mode(__svtypes_rand_stop);
    write.rand_mode(__svtypes_rand_write);
    address.rand_mode(__svtypes_rand_address);
    data.rand_mode(__svtypes_rand_data);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1);
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
    __svtypes_key = (prefix == "") ? "tag=%d" : {prefix, ".tag=%d"};
    if ($test$plusargs((prefix == "") ? "tag" : {prefix, ".tag"}) && !$value$plusargs(__svtypes_key, tag)) $fatal(2, "Malformed plusarg tag");
    __svtypes_key = (prefix == "") ? "stop=%h" : {prefix, ".stop=%h"};
    if ($test$plusargs((prefix == "") ? "stop" : {prefix, ".stop"}) && !$value$plusargs(__svtypes_key, stop)) $fatal(2, "Malformed plusarg stop");
    __svtypes_key = (prefix == "") ? "write=%h" : {prefix, ".write=%h"};
    if ($test$plusargs((prefix == "") ? "write" : {prefix, ".write"}) && !$value$plusargs(__svtypes_key, write)) $fatal(2, "Malformed plusarg write");
    __svtypes_key = (prefix == "") ? "address=%h" : {prefix, ".address=%h"};
    if ($test$plusargs((prefix == "") ? "address" : {prefix, ".address"}) && !$value$plusargs(__svtypes_key, address)) $fatal(2, "Malformed plusarg address");
    __svtypes_key = (prefix == "") ? "data=%h" : {prefix, ".data=%h"};
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
    result = $sformatf("MigrationObservation#%0d{", __svtypes_object_number);
    result = {result, "tag="};
    result = {result, $sformatf("%0d", this.tag)};
    result = {result, ", stop="};
    result = {result, $sformatf("%0h", this.stop)};
    result = {result, ", write="};
    result = {result, $sformatf("%0h", this.write)};
    result = {result, ", address="};
    result = {result, $sformatf("%0h", this.address)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", this.data)};
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
    svtypes_pkg::pack_object_header("project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 5, __svtypes_object_number, bytes);
    svtypes_pkg::int_packer::pack(tag, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(stop, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(write, bytes);
    svtypes_pkg::bit_packer#(bit [7:0])::pack(address, bytes);
    svtypes_pkg::bit_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing MigrationObservation object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing MigrationObservation object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 5, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(tag, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(stop, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(write, bytes, offset);
    svtypes_pkg::bit_packer#(bit [7:0])::unpack(address, bytes, offset);
    svtypes_pkg::bit_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction

  class MigrationObservation__svtypes_coverage;
    covergroup cg with function sample(MigrationObservation item);
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
      address: coverpoint item.address {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_3_ = {[0:3]};
          bins auto_100_103_ = {[100:103]};
          bins auto_104_107_ = {[104:107]};
          bins auto_108_111_ = {[108:111]};
          bins auto_112_115_ = {[112:115]};
          bins auto_116_119_ = {[116:119]};
          bins auto_120_123_ = {[120:123]};
          bins auto_124_127_ = {[124:127]};
          bins auto_128_131_ = {[128:131]};
          bins auto_12_15_ = {[12:15]};
          bins auto_132_135_ = {[132:135]};
          bins auto_136_139_ = {[136:139]};
          bins auto_140_143_ = {[140:143]};
          bins auto_144_147_ = {[144:147]};
          bins auto_148_151_ = {[148:151]};
          bins auto_152_155_ = {[152:155]};
          bins auto_156_159_ = {[156:159]};
          bins auto_160_163_ = {[160:163]};
          bins auto_164_167_ = {[164:167]};
          bins auto_168_171_ = {[168:171]};
          bins auto_16_19_ = {[16:19]};
          bins auto_172_175_ = {[172:175]};
          bins auto_176_179_ = {[176:179]};
          bins auto_180_183_ = {[180:183]};
          bins auto_184_187_ = {[184:187]};
          bins auto_188_191_ = {[188:191]};
          bins auto_192_195_ = {[192:195]};
          bins auto_196_199_ = {[196:199]};
          bins auto_200_203_ = {[200:203]};
          bins auto_204_207_ = {[204:207]};
          bins auto_208_211_ = {[208:211]};
          bins auto_20_23_ = {[20:23]};
          bins auto_212_215_ = {[212:215]};
          bins auto_216_219_ = {[216:219]};
          bins auto_220_223_ = {[220:223]};
          bins auto_224_227_ = {[224:227]};
          bins auto_228_231_ = {[228:231]};
          bins auto_232_235_ = {[232:235]};
          bins auto_236_239_ = {[236:239]};
          bins auto_240_243_ = {[240:243]};
          bins auto_244_247_ = {[244:247]};
          bins auto_248_251_ = {[248:251]};
          bins auto_24_27_ = {[24:27]};
          bins auto_252_255_ = {[252:255]};
          bins auto_28_31_ = {[28:31]};
          bins auto_32_35_ = {[32:35]};
          bins auto_36_39_ = {[36:39]};
          bins auto_40_43_ = {[40:43]};
          bins auto_44_47_ = {[44:47]};
          bins auto_48_51_ = {[48:51]};
          bins auto_4_7_ = {[4:7]};
          bins auto_52_55_ = {[52:55]};
          bins auto_56_59_ = {[56:59]};
          bins auto_60_63_ = {[60:63]};
          bins auto_64_67_ = {[64:67]};
          bins auto_68_71_ = {[68:71]};
          bins auto_72_75_ = {[72:75]};
          bins auto_76_79_ = {[76:79]};
          bins auto_80_83_ = {[80:83]};
          bins auto_84_87_ = {[84:87]};
          bins auto_88_91_ = {[88:91]};
          bins auto_8_11_ = {[8:11]};
          bins auto_92_95_ = {[92:95]};
          bins auto_96_99_ = {[96:99]};
      }
      data: coverpoint item.data {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
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
          bins auto_2147483648_2214592511_ = {[32'h80000000:32'h83ffffff]};
          bins auto_2214592512_2281701375_ = {[32'h84000000:32'h87ffffff]};
          bins auto_2281701376_2348810239_ = {[32'h88000000:32'h8bffffff]};
          bins auto_2348810240_2415919103_ = {[32'h8c000000:32'h8fffffff]};
          bins auto_2415919104_2483027967_ = {[32'h90000000:32'h93ffffff]};
          bins auto_2483027968_2550136831_ = {[32'h94000000:32'h97ffffff]};
          bins auto_2550136832_2617245695_ = {[32'h98000000:32'h9bffffff]};
          bins auto_2617245696_2684354559_ = {[32'h9c000000:32'h9fffffff]};
          bins auto_2684354560_2751463423_ = {[32'ha0000000:32'ha3ffffff]};
          bins auto_268435456_335544319_ = {[268435456:335544319]};
          bins auto_2751463424_2818572287_ = {[32'ha4000000:32'ha7ffffff]};
          bins auto_2818572288_2885681151_ = {[32'ha8000000:32'habffffff]};
          bins auto_2885681152_2952790015_ = {[32'hac000000:32'hafffffff]};
          bins auto_2952790016_3019898879_ = {[32'hb0000000:32'hb3ffffff]};
          bins auto_3019898880_3087007743_ = {[32'hb4000000:32'hb7ffffff]};
          bins auto_3087007744_3154116607_ = {[32'hb8000000:32'hbbffffff]};
          bins auto_3154116608_3221225471_ = {[32'hbc000000:32'hbfffffff]};
          bins auto_3221225472_3288334335_ = {[32'hc0000000:32'hc3ffffff]};
          bins auto_3288334336_3355443199_ = {[32'hc4000000:32'hc7ffffff]};
          bins auto_3355443200_3422552063_ = {[32'hc8000000:32'hcbffffff]};
          bins auto_335544320_402653183_ = {[335544320:402653183]};
          bins auto_3422552064_3489660927_ = {[32'hcc000000:32'hcfffffff]};
          bins auto_3489660928_3556769791_ = {[32'hd0000000:32'hd3ffffff]};
          bins auto_3556769792_3623878655_ = {[32'hd4000000:32'hd7ffffff]};
          bins auto_3623878656_3690987519_ = {[32'hd8000000:32'hdbffffff]};
          bins auto_3690987520_3758096383_ = {[32'hdc000000:32'hdfffffff]};
          bins auto_3758096384_3825205247_ = {[32'he0000000:32'he3ffffff]};
          bins auto_3825205248_3892314111_ = {[32'he4000000:32'he7ffffff]};
          bins auto_3892314112_3959422975_ = {[32'he8000000:32'hebffffff]};
          bins auto_3959422976_4026531839_ = {[32'hec000000:32'hefffffff]};
          bins auto_4026531840_4093640703_ = {[32'hf0000000:32'hf3ffffff]};
          bins auto_402653184_469762047_ = {[402653184:469762047]};
          bins auto_4093640704_4160749567_ = {[32'hf4000000:32'hf7ffffff]};
          bins auto_4160749568_4227858431_ = {[32'hf8000000:32'hfbffffff]};
          bins auto_4227858432_4294967295_ = {[32'hfc000000:32'hffffffff]};
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
      stop: coverpoint item.stop {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_ = {0};
          bins auto_1_ = {1};
      }
      tag: coverpoint item.tag {
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
      write: coverpoint item.write {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_0_ = {0};
          bins auto_1_ = {1};
      }
    endgroup

    function new();
      cg = new();
    endfunction

    function void sample(MigrationObservation item);
      cg.sample(item);
    endfunction

    function real get_coverage();
      return cg.get_coverage();
    endfunction
  endclass
endclass

// SvTypes typed channel helpers
task automatic svx_get_MigrationRequest(string channel_name, output MigrationRequest item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationRequest", "project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1, "svx_get_MigrationRequest", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_MigrationRequest", channel_name, "MigrationRequest", offset, bytes.size());
endtask

task automatic svx_peek_MigrationRequest(string channel_name, output MigrationRequest item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationRequest", "project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1, "svx_peek_MigrationRequest", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_MigrationRequest", channel_name, "MigrationRequest", offset, bytes.size());
endtask

task automatic svx_put_MigrationRequest(string channel_name, input MigrationRequest item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_MigrationRequest(%s): cannot put null SvTypes object type MigrationRequest", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "MigrationRequest", "application/x-svtypes", "project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1);
endtask

task automatic svx_try_get_MigrationRequest(string channel_name, output bit ok, output MigrationRequest item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationRequest", "project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1, "svx_try_get_MigrationRequest", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_MigrationRequest", channel_name, "MigrationRequest", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_MigrationRequest(string channel_name, input MigrationRequest item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_MigrationRequest(%s): cannot put null SvTypes object type MigrationRequest", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "MigrationRequest", "application/x-svtypes", "project_migration.MigrationRequest", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1);
endfunction

task automatic svx_get_MigrationResponse(string channel_name, output MigrationResponse item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationResponse", "project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1, "svx_get_MigrationResponse", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_MigrationResponse", channel_name, "MigrationResponse", offset, bytes.size());
endtask

task automatic svx_peek_MigrationResponse(string channel_name, output MigrationResponse item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationResponse", "project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1, "svx_peek_MigrationResponse", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_MigrationResponse", channel_name, "MigrationResponse", offset, bytes.size());
endtask

task automatic svx_put_MigrationResponse(string channel_name, input MigrationResponse item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_MigrationResponse(%s): cannot put null SvTypes object type MigrationResponse", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "MigrationResponse", "application/x-svtypes", "project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1);
endtask

task automatic svx_try_get_MigrationResponse(string channel_name, output bit ok, output MigrationResponse item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationResponse", "project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1, "svx_try_get_MigrationResponse", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_MigrationResponse", channel_name, "MigrationResponse", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_MigrationResponse(string channel_name, input MigrationResponse item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_MigrationResponse(%s): cannot put null SvTypes object type MigrationResponse", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "MigrationResponse", "application/x-svtypes", "project_migration.MigrationResponse", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1);
endfunction

task automatic svx_get_MigrationObservation(string channel_name, output MigrationObservation item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationObservation", "project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1, "svx_get_MigrationObservation", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_MigrationObservation", channel_name, "MigrationObservation", offset, bytes.size());
endtask

task automatic svx_peek_MigrationObservation(string channel_name, output MigrationObservation item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationObservation", "project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1, "svx_peek_MigrationObservation", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_MigrationObservation", channel_name, "MigrationObservation", offset, bytes.size());
endtask

task automatic svx_put_MigrationObservation(string channel_name, input MigrationObservation item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_MigrationObservation(%s): cannot put null SvTypes object type MigrationObservation", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "MigrationObservation", "application/x-svtypes", "project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1);
endtask

task automatic svx_try_get_MigrationObservation(string channel_name, output bit ok, output MigrationObservation item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "MigrationObservation", "project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1, "svx_try_get_MigrationObservation", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_MigrationObservation", channel_name, "MigrationObservation", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_MigrationObservation(string channel_name, input MigrationObservation item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_MigrationObservation(%s): cannot put null SvTypes object type MigrationObservation", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "MigrationObservation", "application/x-svtypes", "project_migration.MigrationObservation", "866b5f1fc03656fdc86b2daa5c5c73259f8b874d55b653843eacfa1dea1b7369", 1);
endfunction
