from svtypes import Bits, Enum, Int, SvObject, get_package, svobj


m7_pkg = get_package("milestone_7_sv_typed_helpers")


class M7BusOp(Enum):
    M7_OP_READ = 0
    M7_OP_WRITE = 1


@svobj(registry=m7_pkg)
class M7BusReq(SvObject):
    id = Int()
    op = M7BusOp()
    addr = Bits(8)
    data = Bits(32)


@svobj(registry=m7_pkg)
class M7BusRsp(SvObject):
    id = Int()
    ok = Bits(1)
    data = Bits(32)


@svobj(registry=m7_pkg)
class M7BusObs(SvObject):
    id = Int()
    op = M7BusOp()
    addr = Bits(8)
    data = Bits(32)
