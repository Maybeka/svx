import svx
from svtypes import ExternalStorageError
from svx import _native
from svx_mirror.sv_root_pkg import A
from svx_mirror.sv_root_child_pkg import C
from tests.integration.sv_root_target_test import B, constructed

python_c = None


def close(value, fields):
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('released prefix field retained live storage')


@svx.export(name='sv_prefix.direct')
def direct():
    assert A.prefix_scale() == C.prefix_scale() == 800
    plain = A()
    assert not constructed
    assert plain.prefix_count.value == 400 and plain.prefix_virtual() == 400
    assert plain.prefix_value() == 400 and plain.count.value == 11
    close(plain, (plain.prefix_count, plain.count))
    direct_b = B()
    assert constructed.count(direct_b) == 1
    assert direct_b.prefix_virtual() == 423 and direct_b.prefix_value() == 400
    local_retry = direct_b.retry
    close(direct_b, (direct_b.prefix_count, direct_b.count))
    assert local_retry.value == 23 and direct_b.local.value == 7
    svx.display('SV_PREFIX_DIRECT_PASS')


def verify(value):
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert constructed.count(value) == 1
    assert value.prefix_count.value == 400 and value.prefix_value() == 400
    assert value.prefix_virtual() == 423 and value.check() == 135
    assert value.observed_value() == 23


@svx.export(name='sv_prefix.create')
def create():
    global python_c
    python_c = C()
    verify(python_c)
    python_c.prefix_count.value = 410
    assert python_c.prefix_value() == 410 and python_c.prefix_virtual() == 433
    svx.publish_object('sv_prefix.c', python_c)
    svx.display('SV_PREFIX_PYTHON_PASS')


@svx.export(name='sv_prefix.close')
def close_python():
    assert python_c.prefix_value() == 420 and python_c.prefix_virtual() == 443
    close(python_c, (python_c.prefix_count, python_c.count, python_c.retry, python_c.extra))
    assert python_c.local.value == 7
    svx.display('SV_PREFIX_CLOSE_PASS')


@svx.export(name='sv_prefix.verify_sv')
def verify_sv():
    values = [value for value in constructed if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0])
    close(values[0], (values[0].prefix_count, values[0].count, values[0].retry, values[0].extra))
    assert C.prefix_scale() == 800
    svx.display('SV_PREFIX_SV_PASS')
