import svx
from svtypes import Bit, Int, Logic, LongInt


flag = svx.declare_signal("tb.flag", Bit[1]())
data = svx.declare_signal("tb.data", Bit[8]())
logic_data = svx.declare_signal("tb.logic_data", Logic[8]())
signed_data = svx.declare_signal("tb.signed_data", Int())
long_signed_data = svx.declare_signal("tb.long_signed_data", LongInt())
