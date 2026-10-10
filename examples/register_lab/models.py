"""The sole typed transaction contract for the register lab."""

from svtypes import Bit, Int, SvObject, get_package, svobj


lab_package = get_package("register_lab")


@svobj(registry=lab_package)
class RegisterRequest(SvObject):
    tag = Int()
    write = Bit[1]()
    address = Bit[8]()
    data = Bit[32]()


@svobj(registry=lab_package)
class RegisterResponse(SvObject):
    tag = Int()
    data = Bit[32]()


@svobj(registry=lab_package)
class RegisterObservation(SvObject):
    tag = Int()
    write = Bit[1]()
    address = Bit[8]()
    data = Bit[32]()
