import svtypes


class Operation(svtypes.Enum):
    IDLE = 0
    RUN = 3


@svtypes.svobj
class ValuePacket(svtypes.SvStruct):
    tag = svtypes.Bit[8]()
    flags = svtypes.Logic[4]()
