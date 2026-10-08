import svx
from svtypes import Int, ExternalStorageError
from svx import _native
from svx_mirror.same_package_pkg import A

constructed = []


class B(A):
    retry = Int(17)

    def __init__(self):
        super().__init__()
        assert self.retry.value == 17
        self.count.value = 12
        self.retry.value = 23
        constructed.append(self)
        svx.display('PYTHON_FIELD_INITIALIZER_PASS')

    def check(self):
        return super().check() + self.retry.value


def verify_and_close(value):
    assert constructed.count(value) == 1
    assert value.retry.value == value.observed_value() == 23
    assert value.check() == 135
    fields = (value.count, value.retry, value.extra)
    svx.close_instance(value)
    for field in fields:
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('closed field remained accessible')


@svx.export(name='field_default.verify_sv')
def verify_sv():
    values = [value for value in constructed
              if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    verify_and_close(values[0])
    svx.display('FIELD_DEFAULT_SV_PASS')


@svx.export(name='field_default.create')
def create():
    from svx_mirror.same_package_pkg import C
    verify_and_close(C())
    svx.display('FIELD_DEFAULT_PYTHON_PASS')
