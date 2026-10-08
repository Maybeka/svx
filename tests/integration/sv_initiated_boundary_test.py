import svx
from svx import _native
from svtypes import ExternalStorageError, LogicValue
from svx_mirror.field_owner_pkg import Base


constructed = []
sv_created = None


class Derived(Base):
    def __init__(self):
        super().__init__()
        assert self.count.value == 11
        assert self.flags.value == LogicValue.from_string('xz10')
        self.flags.value = LogicValue.from_string('z1x0')
        assert self.get_flags() == LogicValue.from_string('z1x0')
        self.count.value = 12
        constructed.append(self)


@svx.export(name='sv_initiated_boundary.create_python')
def create_python():
    assert not constructed
    identities = []
    for cls in (Base, Derived):
        value = cls()
        assert value.get_count() == (12 if cls is Derived else 11)
        assert value.flags.value == LogicValue.from_string('z1x0' if cls is Derived else 'xz10')
        value.flags.value = LogicValue.from_string('zx01')
        assert value.get_flags() == LogicValue.from_string('zx01')
        value.set_flags(LogicValue.from_string('10zx'))
        assert value.flags.value == LogicValue.from_string('10zx')
        identities.append(value._svx_remote_object_id)
        assert _native.inheritance_get(identities[-1]) is value
        svx.close_instance(value)
        assert _native.inheritance_get(identities[-1]) is None
    assert len(set(identities)) == 2
    assert len(constructed) == 1
    svx.display('SV_INITIATED_BOUNDARY_PYTHON_CREATED')


@svx.export(name='sv_initiated_boundary.verify')
def verify():
    global sv_created
    values = [value for value in constructed
              if _native.inheritance_get(value._svx_remote_object_id) is value]
    assert len(values) == 1
    value = sv_created = values[0]
    assert value.count.value == 12 and value.get_count() == 12
    value.set_count(19)
    assert value.count.value == 19
    assert value.flags.value == LogicValue.from_string('z1x0')
    value.set_flags(LogicValue.from_string('10zx'))
    assert value.flags.value == LogicValue.from_string('10zx')
    svx.display('SV_INITIATED_BOUNDARY_FOUR_STATE_PASS')
    value.retained = value.count
    svx.display('SV_INITIATED_BOUNDARY_BOUND_FIELDS_PASS')


@svx.export(name='sv_initiated_boundary.verify_closed')
def verify_closed():
    value = sv_created
    for field in (value.count, value.retained):
        try:
            _ = field.value
        except ExternalStorageError:
            pass
        else:
            raise AssertionError('SV-only boundary retained live storage after release')
    svx.display('SV_INITIATED_BOUNDARY_RELEASE_PASS')
