"""The sole cross-language transaction schema after the typed-boundary step."""

from svtypes import Bit, Int, SvObject, get_package, svobj

package = get_package("project_migration")


@svobj(registry=package)
class MigrationRequest(SvObject):
    tag = Int()
    stop = Bit[1]()
    write = Bit[1]()
    address = Bit[8]()
    data = Bit[32]()


@svobj(registry=package)
class MigrationResponse(SvObject):
    tag = Int()
    stop = Bit[1]()
    data = Bit[32]()


@svobj(registry=package)
class MigrationObservation(SvObject):
    tag = Int()
    stop = Bit[1]()
    write = Bit[1]()
    address = Bit[8]()
    data = Bit[32]()
