from __future__ import annotations

import os
import svtypes
import svx
from tests.integration.source_chain_base import B


@svx.sv_mirror("sv://source_chain_user_pkg/C")
class CStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class D(CStub, B):
    @svx.inheritance_method
    def check(self, value: svtypes.Int) -> svx.Function[svtypes.Int]:
        return super().check(value) + 10000

    @svx.inheritance_method
    def compute(self, value: svtypes.Int) -> svx.Function[svtypes.Int]:
        return super().compute(value) + 100000


_instance = None
_check_revision = 10 if os.environ.get("SOURCE_CHAIN_BODY_REVISION") == "1" else 0


@svx.export(name="source_chain.create")
def create():
    global _instance
    _instance = D()
    _instance.count.value = 2
    _instance.extra.value = 3
    assert _instance.check(5) == 10117 + _check_revision
    assert _instance.compute(5) == 101008
    if os.environ.get("SOURCE_CHAIN_INTERFACE_REVISION") == "1":
        _instance.bonus.value = 4
        assert _instance.ping(6) == 10
    svx.publish_object("source_chain.instance", _instance)
    svx.display("SOURCE_CHAIN_PYTHON_PASS")


@svx.export(name="source_chain.close")
def close():
    assert _instance.count.value == 7
    assert _instance.extra.value == 11
    assert _instance.check(5) == 10122 + _check_revision
    assert _instance.compute(5) == 101016
    svx.close_instance(_instance)
    svx.display("SOURCE_CHAIN_CLOSE_PASS")
