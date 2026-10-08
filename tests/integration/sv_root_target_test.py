import svx
from svtypes import Int, ExternalStorageError
from svx import _native
from svx_mirror.sv_root_pkg import A


constructed = []
python_c = None
_failure_observer_installed = False


def _install_failure_observer():
    global _failure_observer_installed
    if _failure_observer_installed:
        return
    from svx import inheritance
    original = svx.SVMirror._svx_retire_failed_python_companion
    checked = set()

    def verify_retirement(instance, error):
        original(instance, error)
        if id(instance) in checked or inheritance._natural_constructor_segments.pending_count:
            return
        object_id = instance._svx_remote_object_id
        assert _native.inheritance_get(object_id) is None
        assert object_id not in inheritance._reserved_python_receivers
        for name in instance.__svx_root_field_ids__:
            try:
                _ = getattr(instance, name).value
            except ExternalStorageError:
                pass
            else:
                raise AssertionError("failed constructor retained projected storage")
        checked.add(id(instance))
        print("SV_ROOT_CONSTRUCTOR_ROLLBACK_PYTHON_PASS", flush=True)

    svx.SVMirror._svx_retire_failed_python_companion = verify_retirement
    _failure_observer_installed = True


class B(A):
    retry = Int()
    local = Int()
    fail = False

    def __init__(self):
        super().__init__()
        assert self.count.value == 11
        self.count.value = 12
        self.retry.value = 23
        self.local.value = 7
        if self.fail:
            raise ValueError('SV-root B initializer failed')
        constructed.append(self)

    def check(self):
        return super().check() + self.retry.value

    def prefix_virtual(self):
        return super().prefix_virtual() + self.retry.value


def verify(value):
    assert constructed.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.observed_value() == 23
    assert value.count.value == 12 and value.retry.value == 23 and value.extra.value == 100
    assert value.check() == 135
    assert value.local.value == 7


@svx.export(name='sv_root_target.fail_next_init')
def fail_next_init():
    _install_failure_observer()
    B.fail = True


def close(value):
    fields = (value.count, value.retry, value.extra)
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('closed SV-root target retained live storage')
    assert value.local.value == 7


@svx.export(name='sv_root_target.verify_direct')
def verify_direct():
    assert len(constructed) == 1
    value = constructed[0]
    assert type(value) is B
    assert value.count.value == 12 and value.retry.value == 23
    assert value.check() == 35 and value.local.value == 7
    value.retained_count = value.count
    value.retained_retry = value.retry
    svx.display('SV_ROOT_TARGET_DIRECT_B_PASS')


@svx.export(name='sv_root_target.create_direct')
def create_direct():
    value = B()
    svx.publish_object('sv_root_target.direct_b', value)


@svx.export(name='sv_root_target.verify_direct_closed')
def verify_direct_closed():
    value = constructed[0]
    try:
        _ = value.retained_count.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('direct B retained live A storage')
    assert value.retained_retry.value == 23 and value.local.value == 7
    value.retained_retry.value = 29
    assert value.retry.value == 29
    svx.display('SV_ROOT_TARGET_DIRECT_B_LOCAL_PASS')


@svx.export(name='sv_root_target.create')
def create():
    global python_c
    from svx_mirror.sv_root_child_pkg import C
    python_c = C()
    verify(python_c)
    svx.publish_object('sv_root_target.c', python_c)
    svx.display('SV_ROOT_TARGET_PYTHON_CREATED')


@svx.export(name='sv_root_target.close')
def close_python():
    assert python_c.count.value == 19 and python_c.check() == 142
    close(python_c)
    svx.display('SV_ROOT_TARGET_PYTHON_PASS')


@svx.export(name='sv_root_target.verify_sv')
def verify_sv():
    values = [value for value in constructed if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0])
    close(values[0])
    svx.display('SV_ROOT_TARGET_SV_PASS')


@svx.export(name='sv_root_target.verify_nested')
def verify_nested():
    values = [value for value in constructed if value is not python_c
              and _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0])
    assert values[0]._svx_remote_object_id != python_c._svx_remote_object_id
    close(values[0])
    svx.display('SV_ROOT_CONSTRUCTION_NESTED_PASS')
