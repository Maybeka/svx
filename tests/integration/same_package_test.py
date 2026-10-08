import svx
from svtypes import Int, ExternalStorageError
from svx import _native
from svx_mirror.same_package_pkg import A

constructed = []
python_c = None


class B(A):
    retry = Int()
    local = Int()

    def __init__(self):
        super().__init__()
        assert self.count.value == 11
        self.count.value = 12
        self.retry.value = 23
        self.local.value = 7
        constructed.append(self)

    def check(self):
        return super().check() + self.retry.value


def close(value, fields):
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('same-package field did not become stale')


def verify(value):
    assert constructed.count(value) == 1
    assert _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.check() == 135 and value.observed_value() == 23
    assert value.local.value == 7


@svx.export(name='same_package.direct')
def direct():
    from svx_mirror.same_package_pkg import C
    assert A.scale() == C.scale() == 22
    assert C.__module__ == A.__module__ == 'svx_mirror.same_package_pkg'
    assert C.__qualname__ == C.__name__ == 'C'
    assert not any(_native.inheritance_get(value._svx_remote_object_id) is value for value in constructed)
    value = B()
    assert value.check() == 35
    retry = value.retry
    close(value, (value.count,))
    assert retry.value == 23 and value.local.value == 7
    svx.display('SAME_PACKAGE_DIRECT_PASS')


@svx.export(name='same_package.create')
def create():
    from svx_mirror.same_package_pkg import C
    global python_c
    python_c = C()
    verify(python_c)
    python_c.retry.value = 30
    assert python_c.check() == 142
    svx.publish_object('same_package.c', python_c)
    svx.display('SAME_PACKAGE_PYTHON_PASS')


@svx.export(name='same_package.close')
def close_python():
    assert python_c.extra.value == 110 and python_c.check() == 152
    close(python_c, (python_c.count, python_c.retry, python_c.extra))
    assert python_c.local.value == 7
    svx.display('SAME_PACKAGE_CLOSE_PASS')


@svx.export(name='same_package.verify_sv')
def verify_sv():
    values = [value for value in constructed if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify(values[0])
    close(values[0], (values[0].count, values[0].retry, values[0].extra))
    svx.display('SAME_PACKAGE_SV_PASS')
