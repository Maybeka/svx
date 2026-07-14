import svx
from svtypes import Bits


flag = svx.declare_signal("tb.flag", Bits(1))
data = svx.declare_signal("tb.data", Bits(8))
