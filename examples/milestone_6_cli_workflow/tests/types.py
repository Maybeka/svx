from svtypes import Bit, Enum, Int, SvObject, get_package, svobj


m6_pkg = get_package("milestone_6_cli_workflow")


class M6BusOp(Enum, width=8, signed=False):
    M6_OP_READ = 0
    M6_OP_WRITE = 1


@svobj(registry=m6_pkg)
class M6BusReq(SvObject):
    id = Int()
    op = M6BusOp()
    addr = Bit(8)
    data = Bit(32)


@svobj(registry=m6_pkg)
class M6BusRsp(SvObject):
    id = Int()
    ok = Bit(1)
    data = Bit(32)


@svobj(registry=m6_pkg)
class M6BusObs(SvObject):
    id = Int()
    op = M6BusOp()
    addr = Bit(8)
    data = Bit(32)
