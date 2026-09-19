// Generated from examples.milestone_6_cli_workflow.tests.types
// Do not edit by hand.

typedef enum bit [7:0] {
  M6_OP_READ = 0,
  M6_OP_WRITE = 1
} M6BusOp;

typedef class M6BusReq;
typedef class M6BusRsp;
typedef class M6BusObs;

class M6BusReq extends svtypes_pkg::sv_object;
  rand int id;
  rand M6BusOp op;
  rand bit [7:0] addr;
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
    int __svtypes_rand_id;
    int __svtypes_rand_op;
    int __svtypes_rand_addr;
    int __svtypes_rand_data;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_id = id.rand_mode();
    __svtypes_rand_op = op.rand_mode();
    __svtypes_rand_addr = addr.rand_mode();
    __svtypes_rand_data = data.rand_mode();
    id.rand_mode(0);
    op.rand_mode(0);
    addr.rand_mode(0);
    data.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      id.rand_mode(1);
      op.rand_mode(1);
      addr.rand_mode(1);
      data.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        id.rand_mode(0);
        op.rand_mode(0);
        addr.rand_mode(0);
        data.rand_mode(0);
      end
    end
    id.rand_mode(__svtypes_rand_id);
    op.rand_mode(__svtypes_rand_op);
    addr.rand_mode(__svtypes_rand_addr);
    data.rand_mode(__svtypes_rand_data);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1);
    return descriptor;
  endfunction

  static function svtypes_pkg::runtime_capabilities svtypes_runtime_capabilities();
    return svtypes_pkg::get_runtime_capabilities();
  endfunction

  virtual function void apply_plusargs(string prefix = "");
    string __svtypes_key;
    bit __svtypes_repeated;
    string __svtypes_enum_text_0;
    longint signed __svtypes_enum_value_0;
    __svtypes_repeated = svtypes_pkg::begin_plusarg_object(__svtypes_object_number);
    if (__svtypes_repeated) begin
      svtypes_pkg::end_plusarg_object();
      return;
    end
    __svtypes_key = (prefix == "") ? "id=%d" : {prefix, ".id=%d"};
    if ($test$plusargs((prefix == "") ? "id" : {prefix, ".id"}) && !$value$plusargs(__svtypes_key, id)) $fatal(2, "Malformed plusarg id");
    __svtypes_key = (prefix == "") ? "op=%s" : {prefix, ".op=%s"};
    if ($value$plusargs(__svtypes_key, __svtypes_enum_text_0)) begin
      case (__svtypes_enum_text_0)
        "M6_OP_READ": op = M6_OP_READ;
        "M6_OP_WRITE": op = M6_OP_WRITE;
        default: begin
          if ($sscanf(__svtypes_enum_text_0, "%d", __svtypes_enum_value_0) != 1) $fatal(2, "Malformed enum plusarg op=%s", __svtypes_enum_text_0);
          case (__svtypes_enum_value_0)
            0: op = M6BusOp'(__svtypes_enum_value_0);
            1: op = M6BusOp'(__svtypes_enum_value_0);
            default: $fatal(2, "Invalid enum plusarg op=%s", __svtypes_enum_text_0);
          endcase
        end
      endcase
    end
    __svtypes_key = (prefix == "") ? "addr=%h" : {prefix, ".addr=%h"};
    if ($test$plusargs((prefix == "") ? "addr" : {prefix, ".addr"}) && !$value$plusargs(__svtypes_key, addr)) $fatal(2, "Malformed plusarg addr");
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
    result = $sformatf("M6BusReq#%0d{", __svtypes_object_number);
    result = {result, "id="};
    result = {result, $sformatf("%0d", id)};
    result = {result, ", op="};
    result = {result, $sformatf("M6BusOp.%s", op.name())};
    result = {result, ", addr="};
    result = {result, $sformatf("%0h", addr)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", data)};
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
    svtypes_pkg::pack_object_header("milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 4, __svtypes_object_number, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bit_packer#(M6BusOp)::pack(op, bytes);
    svtypes_pkg::bit_packer#(bit [7:0])::pack(addr, bytes);
    svtypes_pkg::bit_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M6BusReq object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M6BusReq object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 4, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bit_packer#(M6BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bit_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bit_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction

  class M6BusReq__svtypes_coverage;
    covergroup cg with function sample(M6BusReq item);
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
          bins auto_2147483648_2214592511_ = {[2147483648:2214592511]};
          bins auto_2214592512_2281701375_ = {[2214592512:2281701375]};
          bins auto_2281701376_2348810239_ = {[2281701376:2348810239]};
          bins auto_2348810240_2415919103_ = {[2348810240:2415919103]};
          bins auto_2415919104_2483027967_ = {[2415919104:2483027967]};
          bins auto_2483027968_2550136831_ = {[2483027968:2550136831]};
          bins auto_2550136832_2617245695_ = {[2550136832:2617245695]};
          bins auto_2617245696_2684354559_ = {[2617245696:2684354559]};
          bins auto_2684354560_2751463423_ = {[2684354560:2751463423]};
          bins auto_268435456_335544319_ = {[268435456:335544319]};
          bins auto_2751463424_2818572287_ = {[2751463424:2818572287]};
          bins auto_2818572288_2885681151_ = {[2818572288:2885681151]};
          bins auto_2885681152_2952790015_ = {[2885681152:2952790015]};
          bins auto_2952790016_3019898879_ = {[2952790016:3019898879]};
          bins auto_3019898880_3087007743_ = {[3019898880:3087007743]};
          bins auto_3087007744_3154116607_ = {[3087007744:3154116607]};
          bins auto_3154116608_3221225471_ = {[3154116608:3221225471]};
          bins auto_3221225472_3288334335_ = {[3221225472:3288334335]};
          bins auto_3288334336_3355443199_ = {[3288334336:3355443199]};
          bins auto_3355443200_3422552063_ = {[3355443200:3422552063]};
          bins auto_335544320_402653183_ = {[335544320:402653183]};
          bins auto_3422552064_3489660927_ = {[3422552064:3489660927]};
          bins auto_3489660928_3556769791_ = {[3489660928:3556769791]};
          bins auto_3556769792_3623878655_ = {[3556769792:3623878655]};
          bins auto_3623878656_3690987519_ = {[3623878656:3690987519]};
          bins auto_3690987520_3758096383_ = {[3690987520:3758096383]};
          bins auto_3758096384_3825205247_ = {[3758096384:3825205247]};
          bins auto_3825205248_3892314111_ = {[3825205248:3892314111]};
          bins auto_3892314112_3959422975_ = {[3892314112:3959422975]};
          bins auto_3959422976_4026531839_ = {[3959422976:4026531839]};
          bins auto_4026531840_4093640703_ = {[4026531840:4093640703]};
          bins auto_402653184_469762047_ = {[402653184:469762047]};
          bins auto_4093640704_4160749567_ = {[4093640704:4160749567]};
          bins auto_4160749568_4227858431_ = {[4160749568:4227858431]};
          bins auto_4227858432_4294967295_ = {[4227858432:4294967295]};
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
      id: coverpoint item.id {
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
      op: coverpoint item.op {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_M6_OP_READ_ = {M6_OP_READ};
          bins auto_M6_OP_WRITE_ = {M6_OP_WRITE};
      }
    endgroup

    function new();
      cg = new();
    endfunction

    function void sample(M6BusReq item);
      cg.sample(item);
    endfunction

    function real get_coverage();
      return cg.get_coverage();
    endfunction
  endclass
endclass

class M6BusRsp extends svtypes_pkg::sv_object;
  rand int id;
  rand bit [0:0] ok;
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
    int __svtypes_rand_id;
    int __svtypes_rand_ok;
    int __svtypes_rand_data;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_id = id.rand_mode();
    __svtypes_rand_ok = ok.rand_mode();
    __svtypes_rand_data = data.rand_mode();
    id.rand_mode(0);
    ok.rand_mode(0);
    data.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      id.rand_mode(1);
      ok.rand_mode(1);
      data.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        id.rand_mode(0);
        ok.rand_mode(0);
        data.rand_mode(0);
      end
    end
    id.rand_mode(__svtypes_rand_id);
    ok.rand_mode(__svtypes_rand_ok);
    data.rand_mode(__svtypes_rand_data);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1);
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
    __svtypes_key = (prefix == "") ? "id=%d" : {prefix, ".id=%d"};
    if ($test$plusargs((prefix == "") ? "id" : {prefix, ".id"}) && !$value$plusargs(__svtypes_key, id)) $fatal(2, "Malformed plusarg id");
    __svtypes_key = (prefix == "") ? "ok=%h" : {prefix, ".ok=%h"};
    if ($test$plusargs((prefix == "") ? "ok" : {prefix, ".ok"}) && !$value$plusargs(__svtypes_key, ok)) $fatal(2, "Malformed plusarg ok");
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
    result = $sformatf("M6BusRsp#%0d{", __svtypes_object_number);
    result = {result, "id="};
    result = {result, $sformatf("%0d", id)};
    result = {result, ", ok="};
    result = {result, $sformatf("%0h", ok)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", data)};
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
    svtypes_pkg::pack_object_header("milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 3, __svtypes_object_number, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bit_packer#(bit [0:0])::pack(ok, bytes);
    svtypes_pkg::bit_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M6BusRsp object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M6BusRsp object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 3, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bit_packer#(bit [0:0])::unpack(ok, bytes, offset);
    svtypes_pkg::bit_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction

  class M6BusRsp__svtypes_coverage;
    covergroup cg with function sample(M6BusRsp item);
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
          bins auto_2147483648_2214592511_ = {[2147483648:2214592511]};
          bins auto_2214592512_2281701375_ = {[2214592512:2281701375]};
          bins auto_2281701376_2348810239_ = {[2281701376:2348810239]};
          bins auto_2348810240_2415919103_ = {[2348810240:2415919103]};
          bins auto_2415919104_2483027967_ = {[2415919104:2483027967]};
          bins auto_2483027968_2550136831_ = {[2483027968:2550136831]};
          bins auto_2550136832_2617245695_ = {[2550136832:2617245695]};
          bins auto_2617245696_2684354559_ = {[2617245696:2684354559]};
          bins auto_2684354560_2751463423_ = {[2684354560:2751463423]};
          bins auto_268435456_335544319_ = {[268435456:335544319]};
          bins auto_2751463424_2818572287_ = {[2751463424:2818572287]};
          bins auto_2818572288_2885681151_ = {[2818572288:2885681151]};
          bins auto_2885681152_2952790015_ = {[2885681152:2952790015]};
          bins auto_2952790016_3019898879_ = {[2952790016:3019898879]};
          bins auto_3019898880_3087007743_ = {[3019898880:3087007743]};
          bins auto_3087007744_3154116607_ = {[3087007744:3154116607]};
          bins auto_3154116608_3221225471_ = {[3154116608:3221225471]};
          bins auto_3221225472_3288334335_ = {[3221225472:3288334335]};
          bins auto_3288334336_3355443199_ = {[3288334336:3355443199]};
          bins auto_3355443200_3422552063_ = {[3355443200:3422552063]};
          bins auto_335544320_402653183_ = {[335544320:402653183]};
          bins auto_3422552064_3489660927_ = {[3422552064:3489660927]};
          bins auto_3489660928_3556769791_ = {[3489660928:3556769791]};
          bins auto_3556769792_3623878655_ = {[3556769792:3623878655]};
          bins auto_3623878656_3690987519_ = {[3623878656:3690987519]};
          bins auto_3690987520_3758096383_ = {[3690987520:3758096383]};
          bins auto_3758096384_3825205247_ = {[3758096384:3825205247]};
          bins auto_3825205248_3892314111_ = {[3825205248:3892314111]};
          bins auto_3892314112_3959422975_ = {[3892314112:3959422975]};
          bins auto_3959422976_4026531839_ = {[3959422976:4026531839]};
          bins auto_4026531840_4093640703_ = {[4026531840:4093640703]};
          bins auto_402653184_469762047_ = {[402653184:469762047]};
          bins auto_4093640704_4160749567_ = {[4093640704:4160749567]};
          bins auto_4160749568_4227858431_ = {[4160749568:4227858431]};
          bins auto_4227858432_4294967295_ = {[4227858432:4294967295]};
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
      id: coverpoint item.id {
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
      ok: coverpoint item.ok {
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

    function void sample(M6BusRsp item);
      cg.sample(item);
    endfunction

    function real get_coverage();
      return cg.get_coverage();
    endfunction
  endclass
endclass

class M6BusObs extends svtypes_pkg::sv_object;
  rand int id;
  rand M6BusOp op;
  rand bit [7:0] addr;
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
    int __svtypes_rand_id;
    int __svtypes_rand_op;
    int __svtypes_rand_addr;
    int __svtypes_rand_data;
    __svtypes_ok = 1;
    __svtypes_previous_layered_active = __svtypes_layered_randomize_active;
    __svtypes_previous_layered_priority = __svtypes_layered_randomize_priority;
    __svtypes_layered_randomize_active = 1;
    __svtypes_rand_id = id.rand_mode();
    __svtypes_rand_op = op.rand_mode();
    __svtypes_rand_addr = addr.rand_mode();
    __svtypes_rand_data = data.rand_mode();
    id.rand_mode(0);
    op.rand_mode(0);
    addr.rand_mode(0);
    data.rand_mode(0);
    if (__svtypes_ok) begin
      __svtypes_layered_randomize_priority = 0;
      id.rand_mode(1);
      op.rand_mode(1);
      addr.rand_mode(1);
      data.rand_mode(1);
      if (!this.randomize()) begin
        __svtypes_ok = 0;
      end
      else begin
        id.rand_mode(0);
        op.rand_mode(0);
        addr.rand_mode(0);
        data.rand_mode(0);
      end
    end
    id.rand_mode(__svtypes_rand_id);
    op.rand_mode(__svtypes_rand_op);
    addr.rand_mode(__svtypes_rand_addr);
    data.rand_mode(__svtypes_rand_data);
    __svtypes_layered_randomize_active = __svtypes_previous_layered_active;
    __svtypes_layered_randomize_priority = __svtypes_previous_layered_priority;
    return __svtypes_ok;
  endfunction

  static function svtypes_pkg::encoding_descriptor svtypes_encoding_descriptor();
    svtypes_pkg::encoding_descriptor descriptor;
    descriptor = new("milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1);
    return descriptor;
  endfunction

  static function svtypes_pkg::runtime_capabilities svtypes_runtime_capabilities();
    return svtypes_pkg::get_runtime_capabilities();
  endfunction

  virtual function void apply_plusargs(string prefix = "");
    string __svtypes_key;
    bit __svtypes_repeated;
    string __svtypes_enum_text_0;
    longint signed __svtypes_enum_value_0;
    __svtypes_repeated = svtypes_pkg::begin_plusarg_object(__svtypes_object_number);
    if (__svtypes_repeated) begin
      svtypes_pkg::end_plusarg_object();
      return;
    end
    __svtypes_key = (prefix == "") ? "id=%d" : {prefix, ".id=%d"};
    if ($test$plusargs((prefix == "") ? "id" : {prefix, ".id"}) && !$value$plusargs(__svtypes_key, id)) $fatal(2, "Malformed plusarg id");
    __svtypes_key = (prefix == "") ? "op=%s" : {prefix, ".op=%s"};
    if ($value$plusargs(__svtypes_key, __svtypes_enum_text_0)) begin
      case (__svtypes_enum_text_0)
        "M6_OP_READ": op = M6_OP_READ;
        "M6_OP_WRITE": op = M6_OP_WRITE;
        default: begin
          if ($sscanf(__svtypes_enum_text_0, "%d", __svtypes_enum_value_0) != 1) $fatal(2, "Malformed enum plusarg op=%s", __svtypes_enum_text_0);
          case (__svtypes_enum_value_0)
            0: op = M6BusOp'(__svtypes_enum_value_0);
            1: op = M6BusOp'(__svtypes_enum_value_0);
            default: $fatal(2, "Invalid enum plusarg op=%s", __svtypes_enum_text_0);
          endcase
        end
      endcase
    end
    __svtypes_key = (prefix == "") ? "addr=%h" : {prefix, ".addr=%h"};
    if ($test$plusargs((prefix == "") ? "addr" : {prefix, ".addr"}) && !$value$plusargs(__svtypes_key, addr)) $fatal(2, "Malformed plusarg addr");
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
    result = $sformatf("M6BusObs#%0d{", __svtypes_object_number);
    result = {result, "id="};
    result = {result, $sformatf("%0d", id)};
    result = {result, ", op="};
    result = {result, $sformatf("M6BusOp.%s", op.name())};
    result = {result, ", addr="};
    result = {result, $sformatf("%0h", addr)};
    result = {result, ", data="};
    result = {result, $sformatf("%0h", data)};
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
    svtypes_pkg::pack_object_header("milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 4, __svtypes_object_number, bytes);
    svtypes_pkg::int_packer::pack(id, bytes);
    svtypes_pkg::bit_packer#(M6BusOp)::pack(op, bytes);
    svtypes_pkg::bit_packer#(bit [7:0])::pack(addr, bytes);
    svtypes_pkg::bit_packer#(bit [31:0])::pack(data, bytes);
  endfunction

  virtual function void unpack(ref byte unsigned bytes[$], ref int offset);
    byte unsigned present;
    svtypes_pkg::require_available(bytes, offset, 1, "object presence");
    present = bytes[offset];
    offset += 1;
    if (present == 8'h02) begin
      $fatal(2, "SvTypes cannot unpack root reference into existing M6BusObs object");
    end
    if (present != 8'h01) begin
      $fatal(2, "SvTypes cannot unpack null into existing M6BusObs object");
    end
    unpack_body(bytes, offset);
  endfunction

  virtual function void unpack_body(ref byte unsigned bytes[$], ref int offset);
    longint unsigned incoming_svtypes_object_number;
    svtypes_pkg::unpack_object_header("milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 4, incoming_svtypes_object_number, bytes, offset);
    __svtypes_object_number = incoming_svtypes_object_number;
    svtypes_pkg::register_object(this);
    svtypes_pkg::int_packer::unpack(id, bytes, offset);
    svtypes_pkg::bit_packer#(M6BusOp)::unpack(op, bytes, offset);
    svtypes_pkg::bit_packer#(bit [7:0])::unpack(addr, bytes, offset);
    svtypes_pkg::bit_packer#(bit [31:0])::unpack(data, bytes, offset);
  endfunction

  class M6BusObs__svtypes_coverage;
    covergroup cg with function sample(M6BusObs item);
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
          bins auto_2147483648_2214592511_ = {[2147483648:2214592511]};
          bins auto_2214592512_2281701375_ = {[2214592512:2281701375]};
          bins auto_2281701376_2348810239_ = {[2281701376:2348810239]};
          bins auto_2348810240_2415919103_ = {[2348810240:2415919103]};
          bins auto_2415919104_2483027967_ = {[2415919104:2483027967]};
          bins auto_2483027968_2550136831_ = {[2483027968:2550136831]};
          bins auto_2550136832_2617245695_ = {[2550136832:2617245695]};
          bins auto_2617245696_2684354559_ = {[2617245696:2684354559]};
          bins auto_2684354560_2751463423_ = {[2684354560:2751463423]};
          bins auto_268435456_335544319_ = {[268435456:335544319]};
          bins auto_2751463424_2818572287_ = {[2751463424:2818572287]};
          bins auto_2818572288_2885681151_ = {[2818572288:2885681151]};
          bins auto_2885681152_2952790015_ = {[2885681152:2952790015]};
          bins auto_2952790016_3019898879_ = {[2952790016:3019898879]};
          bins auto_3019898880_3087007743_ = {[3019898880:3087007743]};
          bins auto_3087007744_3154116607_ = {[3087007744:3154116607]};
          bins auto_3154116608_3221225471_ = {[3154116608:3221225471]};
          bins auto_3221225472_3288334335_ = {[3221225472:3288334335]};
          bins auto_3288334336_3355443199_ = {[3288334336:3355443199]};
          bins auto_3355443200_3422552063_ = {[3355443200:3422552063]};
          bins auto_335544320_402653183_ = {[335544320:402653183]};
          bins auto_3422552064_3489660927_ = {[3422552064:3489660927]};
          bins auto_3489660928_3556769791_ = {[3489660928:3556769791]};
          bins auto_3556769792_3623878655_ = {[3556769792:3623878655]};
          bins auto_3623878656_3690987519_ = {[3623878656:3690987519]};
          bins auto_3690987520_3758096383_ = {[3690987520:3758096383]};
          bins auto_3758096384_3825205247_ = {[3758096384:3825205247]};
          bins auto_3825205248_3892314111_ = {[3825205248:3892314111]};
          bins auto_3892314112_3959422975_ = {[3892314112:3959422975]};
          bins auto_3959422976_4026531839_ = {[3959422976:4026531839]};
          bins auto_4026531840_4093640703_ = {[4026531840:4093640703]};
          bins auto_402653184_469762047_ = {[402653184:469762047]};
          bins auto_4093640704_4160749567_ = {[4093640704:4160749567]};
          bins auto_4160749568_4227858431_ = {[4160749568:4227858431]};
          bins auto_4227858432_4294967295_ = {[4227858432:4294967295]};
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
      id: coverpoint item.id {
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
      op: coverpoint item.op {
          option.at_least = 1;
          option.auto_bin_max = 64;
          option.comment = "";
          option.detect_overlap = 0;
          option.goal = 100;
          option.weight = 1;
          bins auto_M6_OP_READ_ = {M6_OP_READ};
          bins auto_M6_OP_WRITE_ = {M6_OP_WRITE};
      }
    endgroup

    function new();
      cg = new();
    endfunction

    function void sample(M6BusObs item);
      cg.sample(item);
    endfunction

    function real get_coverage();
      return cg.get_coverage();
    endfunction
  endclass
endclass

// SvTypes typed channel helpers
task automatic svx_get_M6BusReq(string channel_name, output M6BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusReq", "milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1, "svx_get_M6BusReq", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_M6BusReq", channel_name, "M6BusReq", offset, bytes.size());
endtask

task automatic svx_peek_M6BusReq(string channel_name, output M6BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusReq", "milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1, "svx_peek_M6BusReq", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_M6BusReq", channel_name, "M6BusReq", offset, bytes.size());
endtask

task automatic svx_put_M6BusReq(string channel_name, input M6BusReq item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_M6BusReq(%s): cannot put null SvTypes object type M6BusReq", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M6BusReq", "application/x-svtypes", "milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1);
endtask

task automatic svx_try_get_M6BusReq(string channel_name, output bit ok, output M6BusReq item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusReq", "milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1, "svx_try_get_M6BusReq", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_M6BusReq", channel_name, "M6BusReq", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_M6BusReq(string channel_name, input M6BusReq item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_M6BusReq(%s): cannot put null SvTypes object type M6BusReq", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M6BusReq", "application/x-svtypes", "milestone_6_cli_workflow.M6BusReq", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1);
endfunction

task automatic svx_get_M6BusRsp(string channel_name, output M6BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusRsp", "milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1, "svx_get_M6BusRsp", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_M6BusRsp", channel_name, "M6BusRsp", offset, bytes.size());
endtask

task automatic svx_peek_M6BusRsp(string channel_name, output M6BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusRsp", "milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1, "svx_peek_M6BusRsp", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_M6BusRsp", channel_name, "M6BusRsp", offset, bytes.size());
endtask

task automatic svx_put_M6BusRsp(string channel_name, input M6BusRsp item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_M6BusRsp(%s): cannot put null SvTypes object type M6BusRsp", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M6BusRsp", "application/x-svtypes", "milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1);
endtask

task automatic svx_try_get_M6BusRsp(string channel_name, output bit ok, output M6BusRsp item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusRsp", "milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1, "svx_try_get_M6BusRsp", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_M6BusRsp", channel_name, "M6BusRsp", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_M6BusRsp(string channel_name, input M6BusRsp item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_M6BusRsp(%s): cannot put null SvTypes object type M6BusRsp", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M6BusRsp", "application/x-svtypes", "milestone_6_cli_workflow.M6BusRsp", "051000b62407a733c3b7692a62a481d3d7217358946a4bf18270e6586c2b0501", 1);
endfunction

task automatic svx_get_M6BusObs(string channel_name, output M6BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_get_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusObs", "milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1, "svx_get_M6BusObs", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_get_M6BusObs", channel_name, "M6BusObs", offset, bytes.size());
endtask

task automatic svx_peek_M6BusObs(string channel_name, output M6BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  svx_pkg::svx_channel_peek_payload(channel_name, payload);
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusObs", "milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1, "svx_peek_M6BusObs", bytes);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_peek_M6BusObs", channel_name, "M6BusObs", offset, bytes.size());
endtask

task automatic svx_put_M6BusObs(string channel_name, input M6BusObs item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_put_M6BusObs(%s): cannot put null SvTypes object type M6BusObs", channel_name);
  end
  item.pack(bytes);
  svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "M6BusObs", "application/x-svtypes", "milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1);
endtask

task automatic svx_try_get_M6BusObs(string channel_name, output bit ok, output M6BusObs item);
  chandle payload;
  byte unsigned bytes[$];
  int offset;
  payload = svx_pkg::svx_channel_try_get_payload(channel_name);
  if (payload == null) begin
    ok = 0;
    item = null;
    return;
  end
  svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "M6BusObs", "milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1, "svx_try_get_M6BusObs", bytes);
  svx_pkg::svx_payload_destroy(payload);
  item = new();
  offset = 0;
  item.unpack(bytes, offset);
  svx_pkg::svx_require_unpacked_all("svx_try_get_M6BusObs", channel_name, "M6BusObs", offset, bytes.size());
  ok = 1;
endtask

function automatic bit svx_try_put_M6BusObs(string channel_name, input M6BusObs item);
  byte unsigned bytes[$];
  if (item == null) begin
    $fatal(2, "svx_try_put_M6BusObs(%s): cannot put null SvTypes object type M6BusObs", channel_name);
  end
  item.pack(bytes);
  return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "M6BusObs", "application/x-svtypes", "milestone_6_cli_workflow.M6BusObs", "497dcdfe1a842611aac0ced5a1ddf81ccae1ea2cc58b02cfd433199b39743809", 1);
endfunction
