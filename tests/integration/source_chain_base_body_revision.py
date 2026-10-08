from __future__ import annotations

import svtypes
import svx


@svx.sv_mirror("sv://source_chain_pkg/A")
class AStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class B(AStub):
    extra = svtypes.Int()

    @svx.inheritance_method
    def check(self, value: svtypes.Int) -> svx.Function[svtypes.Int]:
        return super().check(value) + 20

    @svx.inheritance_method
    def compute(self, value: svtypes.Int) -> svx.Function[svtypes.Int]:
        return self.extra.value + value
