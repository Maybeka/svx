import svx
from svtypes import Bit, Int, Logic

flag = svx.declare_signal("tb.flag", Bit[1]())
data = svx.declare_signal("tb.data", Bit[32]())
constant = svx.declare_signal("tb.constant_data", Bit[32]())
wide = svx.declare_signal("tb.wide", Logic[65]())
huge = svx.declare_signal("tb.huge", Logic[128]())
net = svx.declare_signal("tb.observed", Logic[8]())
driver = svx.declare_signal("tb.driver", Logic[8]())
scalar = svx.declare_signal("tb.scalar", Logic[1]())
signed = svx.declare_signal("tb.signed_data", Int())
