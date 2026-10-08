import svx
import svx.inheritance as inheritance
from svx import _native
from svx_mirror.same_package_pkg import A


def check(self):
    object_id = self._svx_remote_object_id
    svx.close_instance(self)
    assert _native.inheritance_get(object_id) is None
    assert object_id not in inheritance._reserved_python_receivers
    svx.display('EARLY_LITERAL_RELEASE_CLEAN_PASS')
    return 11


A.check = check


@svx.export(name='early_literal_close.create')
def create():
    A()
    raise AssertionError('closed literal mirror construction unexpectedly succeeded')
