"""User-side later Python portion for the internal Python-root chain fixture."""

from svtypes import Int
from svx_mirror.python_root_probe_pkg import Child
from tests.integration.python_root_proxy_test import Root


class Derived(Child, Root):
    own_value = Int()

    def __init__(self, child_seed):
        super().__init__(child_seed)
        assert self.observed_value() == child_seed
        assert self.own_value.value == 0
        self.own_value.value = 1000
        if child_seed == 88:
            raise ValueError("derived initializer failed after C construction")

    def check(self, delta):
        return super().check(delta) + self.own_value.value
