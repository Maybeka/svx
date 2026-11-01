"""One package combines an alternating chain and an ordinary SV class family."""

import svx
from svtypes import Int

constructed = []


@svx.sv_mirror('sv://export_chain_pkg/A')
class AStub(svx.SVMirror):
    pass


@svx.inheritance_class()
class B(AStub):
    bonus = Int()

    def __init__(self):
        super().__init__()
        self.seed.value = 12
        self.bonus.value = 23
        constructed.append(self)

    def check(self):
        return super().check() + self.bonus.value


@svx.export(name='package_chain.run')
def run():
    from svx_mirror.export_chain_pkg import A, C, CLeaf, NativeBase, NativeDriver

    class PythonDriver(NativeDriver):
        def check(self):
            return super().check() + 100

    assert issubclass(B, A) and issubclass(C, B)
    assert CLeaf.__bases__ == (C,)
    assert issubclass(NativeDriver, NativeBase)
    base = A()
    assert base.seed.value == 11 and base.check() == 11
    assert not constructed
    svx.close_instance(base)
    chain = CLeaf()
    assert constructed == [chain]
    assert chain.check() == 142
    assert chain.seed.value == 12 and chain.bonus.value == 23 and chain.extra.value == 100
    assert chain.leaf.value == 7
    driver = PythonDriver()
    assert isinstance(driver, NativeBase)
    assert driver.value.value == 41 and driver.check() == 142
    assert NativeBase.check(driver) == 41
    driver.value.value = 42
    assert driver.check() == 143
    svx.publish_object('package_chain.native', driver)
    svx.publish_object('package_chain.chain', chain)
    svx.display('PACKAGE_CHAIN_PYTHON_PASS')
