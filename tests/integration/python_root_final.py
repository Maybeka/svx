"""User Python portion after the second SV boundary in the root-chain fixture."""

from svtypes import Int
from svx_mirror.python_root_probe_pkg import Grandchild


class Final(Grandchild):
    f_value = Int()

    def __init__(self, f_seed):
        super().__init__(f_seed)
        self.f_value.value = 3000

    def check(self, delta):
        return super().check(delta) + self.f_value.value
