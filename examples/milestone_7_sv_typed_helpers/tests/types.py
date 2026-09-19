from svtypes import Bit, Enum, Int, SvObject, get_package, svobj


m7_pkg = get_package("milestone_7_sv_typed_helpers")


class M7BusOp(Enum, width=8, signed=False):
    M7_OP_READ = 0
    M7_OP_WRITE = 1


@svobj(registry=m7_pkg)
class M7BusReq(SvObject):
    id = Int()
    op = M7BusOp()
    addr = Bit(8)
    data = Bit(32)


@svobj(registry=m7_pkg)
class M7BusRsp(SvObject):
    id = Int()
    ok = Bit(1)
    data = Bit(32)


@svobj(registry=m7_pkg)
class M7BusObs(SvObject):
    id = Int()
    op = M7BusOp()
    addr = Bit(8)
    data = Bit(32)
