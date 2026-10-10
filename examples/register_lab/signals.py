"""Sparse setup/diagnostic access, declared before Python tests start."""

import svx
from svtypes import Bit, Logic


cookie = svx.declare_signal("tb.dut.debug_cookie", Bit[32]())
status = svx.declare_signal("tb.debug_status", Logic[8]())
read_data = svx.declare_signal("tb.bus.rdata", Logic[32]())
