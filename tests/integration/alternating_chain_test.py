from svtypes import Int

import svx
from svx import inheritance_class
from svx_mirror.chain_pkg import A
from svx_mirror.chain_user_pkg import C


base_callbacks = 0


@inheritance_class(
    canonical_id="py://tests/integration/alternating_chain/B",
    constructor_initiator="python",
)
class B(A):
    retry = Int()

    def base_check(self):
        global base_callbacks
        base_callbacks += 1


@inheritance_class(
    canonical_id="py://tests/integration/alternating_chain/D",
    constructor_initiator="python",
)
class D(C, B):
    def __init__(self):
        super().__init__()
        self.retry.value = 23
        self.c_check()
        self.trigger_base_check()


@svx.export(name="alternating_chain.run")
def run():
    value = D()
    if value.retry.value != 23:
        raise AssertionError("B projected field is not bound through CMirror")
    if base_callbacks != 1:
        raise AssertionError("C did not dispatch A virtual method to the B Python implementation")


@svx.export(name="alternating_chain.verify_direct_c")
def verify_direct_c():
    if base_callbacks != 2:
        raise AssertionError("SV-created C did not dispatch through the B Python companion")
