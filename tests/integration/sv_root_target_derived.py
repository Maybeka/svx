from svtypes import Int, ExternalStorageError
import svx
from svx import _native
from svx_mirror.sv_root_child_pkg import C
from tests.integration.sv_root_target_test import B, constructed


derived = []
python_d = None
python_e = None


class D(C, B):
    own = Int()
    fail_late = False

    def __init__(self):
        super().__init__()
        assert self.observed_value() == 23
        assert constructed.count(self) == 1
        self.own.value = 1000
        if self.fail_late:
            raise ValueError('SV-root D initializer failed after C')
        derived.append(self)

    def check(self):
        return super().check() + self.own.value


@svx.export(name='sv_root_target.fail_next_late_init')
def fail_next_late_init():
    from tests.integration.sv_root_target_test import _install_failure_observer
    _install_failure_observer()
    D.fail_late = True


@svx.export(name='sv_root_target.create_d')
def create_d():
    global python_d
    python_d = D()
    assert python_d.check() == 1135
    assert derived.count(python_d) == 1 and constructed.count(python_d) == 1
    svx.publish_object('sv_root_target.d', python_d)
    svx.display('SV_ROOT_TARGET_D_CREATED')


@svx.export(name='sv_root_target.close_d')
def close_d():
    field, own = python_d.count, python_d.own
    svx.close_instance(python_d)
    try:
        _ = field.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('D retained live C storage')
    assert own.value == 1000
    own.value = 2000
    assert python_d.own.value == 2000
    svx.display('SV_ROOT_TARGET_D_LOCAL_PASS')


def verify_e(value):
    assert constructed.count(value) == 1 and derived.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.observed_value() == 23 and value.observed_python() == 1000
    assert value.check() == 1635 and value.e_value.value == 500


def close_e(value):
    fields = (value.count, value.retry, value.extra, value.own, value.e_value)
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('E retained live projected storage')
    assert value.local.value == 7


@svx.export(name='sv_root_target.create_e')
def create_e():
    global python_e
    from svx_mirror.sv_root_e_pkg import E
    python_e = E()
    verify_e(python_e)
    svx.publish_object('sv_root_target.e', python_e)
    svx.display('SV_ROOT_TARGET_E_CREATED')


@svx.export(name='sv_root_target.close_e')
def close_python_e():
    assert python_e.own.value == 2000 and python_e.check() == 2635
    close_e(python_e)
    svx.display('SV_ROOT_TARGET_E_PYTHON_PASS')


@svx.export(name='sv_root_target.verify_sv_e')
def verify_sv_e():
    values = [value for value in derived if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify_e(values[0])
    close_e(values[0])
    svx.display('SV_ROOT_TARGET_E_SV_PASS')
