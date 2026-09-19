import svx
from svtypes import Bit, Logic


ready = svx.declare_signal("tb.ready", Bit(1))
data = svx.declare_signal("tb.data", Bit(8))
status = svx.declare_signal("tb.status", Logic(8))
