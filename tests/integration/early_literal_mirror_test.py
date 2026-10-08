import svx
from svtypes import ExternalStorageError
from svx import _native
from svx_mirror.same_package_pkg import A

seen = []
original_check = A.check


def check(self):
    if not any(value is self for value in seen):
        seen.append(self)
    return original_check(self)


A.check = check


def close(value):
    field = value.count
    svx.close_instance(value)
    assert _native.inheritance_get(value._svx_remote_object_id) is None
    try:
        _ = field.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('literal mirror close did not invalidate its field')


@svx.export(name='early_literal.create')
def create():
    value = A()
    assert type(value) is A and seen == [value]
    assert value.check() == 11
    value.count.value = 19
    assert value.check() == 19
    close(value)
    svx.display('EARLY_LITERAL_PYTHON_PASS')


@svx.export(name='early_literal.verify_sv')
def verify_sv():
    assert len(seen) == 2 and seen[0] is not seen[1]
    value = seen[-1]
    assert type(value) is A and _native.inheritance_get(value._svx_remote_object_id) is value
    assert value.check() == 11
    close(value)
    svx.display('EARLY_LITERAL_SV_PASS')
