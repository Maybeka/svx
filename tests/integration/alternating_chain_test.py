from svtypes import Int
import os

import svx
from svx import inheritance_class
from svx_mirror.chain_pkg import A
from svx_mirror.chain_user_pkg import C


base_callbacks = 0
new_callbacks = 0


@inheritance_class(
    canonical_id="py://tests/integration/alternating_chain/B",
    constructor_initiator="python",
)
class B(A):
    retry = Int()
    static_waits = 0

    @staticmethod
    def scale(delta):
        return delta * 3

    @staticmethod
    def wait_once():
        svx.delay(2, 'ns')
        B.static_waits += 1

    def base_check(self):
        global base_callbacks
        super().base_check()
        self.count.value += 1
        base_callbacks += 1

    def b_check(self):
        global new_callbacks
        new_callbacks += 1


@inheritance_class(
    canonical_id="py://tests/integration/alternating_chain/D",
    constructor_initiator="python",
)
class D(C, B):
    @staticmethod
    def scale(delta):
        return delta * 7

    def __init__(self):
        super().__init__()
        if self.count.value != 11:
            raise AssertionError("D cannot access the initialized A field")
        self.count.value = 31
        self.retry.value = 23
        self.c_check()
        if self.count.value != 37:
            raise AssertionError("D cannot see C's write to inherited A.count")
        self.trigger_base_check()
        if self.count.value != 48:
            raise AssertionError("B callback did not share D's inherited field storage")


@svx.export(name="alternating_chain.run")
def run():
    if os.getenv('SVX_ALTERNATING_STATIC') == '1':
        assert B.scale(7) == 21
        assert C.scale(7) == 35
        assert D.scale(7) == 49
        assert B.static_waits == 2
        svx.display('ALTERNATING_STATIC_SHADOW_PASS')
    value = D()
    if value.retry.value != 23:
        raise AssertionError("B projected field is not bound through CMirror")
    if base_callbacks != 1:
        raise AssertionError("C did not dispatch A virtual method to the B Python implementation")
    if new_callbacks != 1:
        raise AssertionError("C did not dispatch B's newly introduced virtual method")


@svx.export(name="alternating_chain.verify_direct_c")
def verify_direct_c():
    if base_callbacks != 2:
        raise AssertionError("SV-created C did not dispatch through the B Python companion")
    if new_callbacks != 2:
        raise AssertionError("SV-created C did not dispatch B's new method")
