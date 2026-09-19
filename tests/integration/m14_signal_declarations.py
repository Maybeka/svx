import svx
from svtypes import Bit, Logic


flag = svx.declare_signal("tb.flag", Bit(1))
data = svx.declare_signal("tb.data", Bit(8))
logic_data = svx.declare_signal("tb.logic_data", Logic(8))
