import svx
from svx import _native
from svtypes import ExternalStorageError
from svx_mirror.sv_root_child_pkg import C
from tests.integration.sv_root_target_test import constructed

python_value = None


def verify(value):
    assert constructed.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.middle.value == 300 and value.middle_value() == 300
    assert value.check() == 435 and value.observed_value() == 23
    assert value.local.value == 7
    assert value.middle_scale(7) == 21 and value.scale(7) == 28


@svx.export(name='ordinary_middle.static')
def static():
    assert not constructed
    assert C.middle_scale(7) == 21 and C.scale(7) == 28
    assert C.root_scale(7) == 14
    C.middle_wait()
    assert not constructed
    svx.display('ORDINARY_MIDDLE_STATIC_PASS')


@svx.export(name='ordinary_middle.static_after_close')
def static_after_close():
    assert C.middle_scale(7) == 21 and C.scale(7) == 28
    assert C.root_scale(7) == 14
    C.middle_wait()
    svx.display('ORDINARY_MIDDLE_STATIC_CLOSED_PASS')


def close(value):
    fields = value.count, value.retry, value.middle, value.extra
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('ordinary middle retained live projected field')
    assert value.local.value == 7


@svx.export(name='ordinary_middle.create')
def create():
    global python_value
    python_value = C()
    verify(python_value)
    python_value.middle.value = 310
    assert python_value.middle_value() == 310 and python_value.check() == 445
    svx.publish_object('ordinary_middle.c', python_value)
    svx.display('ORDINARY_MIDDLE_PYTHON_PASS')


@svx.export(name='ordinary_middle.close')
def close_python():
    assert python_value.middle.value == 320
    assert python_value.middle_value() == 320 and python_value.check() == 455
    close(python_value)
    svx.display('ORDINARY_MIDDLE_CLOSE_PASS')


@svx.export(name='ordinary_middle.verify_sv')
def verify_sv():
    live = [value for value in constructed if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(live) == 1
    verify(live[0])
    close(live[0])
    svx.display('ORDINARY_MIDDLE_SV_PASS')
