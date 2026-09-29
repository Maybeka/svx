import svx
from svtypes import Bit, Int


missing_a = svx.declare_signal("tb.missing_a", Bit[1]())
missing_b = svx.declare_signal("tb.missing_b", Bit[8]())
signedness_mismatch = svx.declare_signal("tb.unsigned_data", Int())
