"""Fixed startup metadata contract, independent of Python test definitions."""

from svtypes import Bit, String, SvObject, svobj


@svobj
class UvmxRegistration(SvObject):
    canonical_id = String(cov=False)
    factory_name = String(cov=False)
    sv_base = String(cov=False)
    finished = Bit[1](cov=False)
