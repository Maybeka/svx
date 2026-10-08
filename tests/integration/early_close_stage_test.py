import svx
import svx.inheritance as inheritance
from svx import _native
from tests.integration import field_default_stage_test as source


def check(self):
    object_id = self._svx_remote_object_id
    svx.close_instance(self)
    assert _native.inheritance_get(object_id) is None
    assert object_id not in inheritance._reserved_python_receivers
    assert not source.constructed
    svx.display('EARLY_RELEASE_RESERVATION_CLEAN_PASS')
    return 11


source.B.check = check


@svx.export(name='early_close.create')
def create():
    from svx_mirror.same_package_pkg import C
    C()
    raise AssertionError('closed receiver construction unexpectedly succeeded')
