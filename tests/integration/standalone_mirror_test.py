import svx
from svx import _native
from svx_mirror.field_owner_pkg import Base


class Derived(Base):
    pass


@svx.export(name='standalone_mirror.run')
def run():
    value = Derived()
    object_id = value._svx_remote_object_id
    assert value.get_count() == 11
    value.set_count(41)
    Base.__init__(value)
    assert value._svx_remote_object_id == object_id
    assert value.get_count() == 41, 'bound initialization replaced the backing SV object'
    assert _native.inheritance_get(object_id) is value
    svx.close_instance(value)
    assert _native.inheritance_get(object_id) is None
    svx.display('STANDALONE_MIRROR_PASS')
