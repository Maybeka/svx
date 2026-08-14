import svx
from svtypes import Bits, LogicBits


flag = svx.declare_signal("tb.flag", Bits(1))
data = svx.declare_signal("tb.data", Bits(8))
logic_data = svx.declare_signal("tb.logic_data", LogicBits(8))
