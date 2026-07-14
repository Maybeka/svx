from svtypes import Bits, Enum, Int, SvObject, get_package, svobj


m5_pkg = get_package("milestone_5_existing_env")


class M5BusOp(Enum):
    M5_OP_READ = 0
    M5_OP_WRITE = 1


@svobj(registry=m5_pkg)
class M5BusReq(SvObject):
    id = Int()
    op = M5BusOp()
    addr = Bits(8)
    data = Bits(32)


@svobj(registry=m5_pkg)
class M5BusRsp(SvObject):
    id = Int()
    ok = Bits(1)
    data = Bits(32)


@svobj(registry=m5_pkg)
class M5BusObs(SvObject):
    id = Int()
    op = M5BusOp()
    addr = Bits(8)
    data = Bits(32)
