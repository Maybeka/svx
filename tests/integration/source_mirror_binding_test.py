import importlib
import os

import svx
from svx import _native

if os.environ.get("SOURCE_MIRROR_LOAD_ORDER") == "generated-first":
    importlib.import_module("svx_mirror.field_owner_pkg")


@svx.sv_mirror("sv://field_owner_pkg/Base")
class BaseStub(svx.SVMirror):
    pass


class Derived(BaseStub):
    def __init__(self):
        super().__init__()

    def get_count(self):
        return super().get_count() + 1


if os.environ.get("SOURCE_MIRROR_LOAD_ORDER") != "artifact":
    importlib.import_module("svx_mirror.field_owner_pkg")


@svx.export(name="source_mirror.run")
def run():
    assert Derived.__bases__ == (BaseStub,)
    value = Derived()
    assert value.get_count() == 12
    value.set_count(41)
    assert value.get_count() == 42
    if os.environ.get("SOURCE_MIRROR_FIELDS") == "1":
        assert value.count.value == 41
        value.count.value = 43
        assert value.get_count() == 44
        svx.display("SOURCE_MIRROR_FIELD_BINDING_PASS")
    object_id = value._svx_remote_object_id
    assert _native.inheritance_get(object_id) is value
    svx.close_instance(value)
    assert _native.inheritance_get(object_id) is None
    if os.environ.get("SOURCE_MIRROR_FIELDS") == "1":
        class Failed(Derived):
            last_id = None

            def __init__(self):
                super().__init__()
                type(self).last_id = self._svx_remote_object_id
                self.count.value = 54
                raise ValueError("source mirror initialization failed")

        try:
            Failed()
        except ValueError as error:
            assert str(error) == "source mirror initialization failed"
        else:
            raise AssertionError("failed initializer unexpectedly returned")
        assert Failed.last_id is not None
        assert _native.inheritance_get(Failed.last_id) is None
        svx.display("SOURCE_MIRROR_FAILURE_CLEANUP_PASS")
    svx.display("SOURCE_MIRROR_BINDING_PASS")
