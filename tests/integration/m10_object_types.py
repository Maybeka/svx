from svtypes import Int, String, SvObject, svobj


@svobj
class Packet(SvObject):
    address = Int()
    label = String()
