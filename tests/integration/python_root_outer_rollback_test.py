import svx
from svx import _native
from svtypes import ExternalStorageError
from tests.integration.python_root_derived import Derived
from tests.integration.python_root_proxy_test import constructed_roots

failed = []


class Reinitialized(Derived):
    fail_again = False

    def __init__(self, seed):
        if self._svx_remote_object_id is None:
            super().__init__(seed)
        if self.fail_again:
            raise ValueError('existing Python-root initializer failed')


class Failed(Derived):
    def __init__(self, seed):
        try:
            super().__init__(seed)
        except ValueError:
            assert self.observed_value() == seed
            assert self.own_value.value == 1000
            failed.append((self, self.count, self.child_value))
            svx.publish_object('python_root_outer.failed', self)
            raise


@svx.export(name='python_root_outer.run')
def run():
    for _ in range(2):
        try:
            Failed(88)
        except ValueError as error:
            assert str(error) == 'derived initializer failed after C construction'
        else:
            raise AssertionError('failed Python-root outer initializer returned')
    assert len({entry[0]._svx_remote_object_id for entry in failed}) == 2
    for value, *fields in failed:
        assert constructed_roots.count(value) == 1
        assert _native.inheritance_get(value._svx_remote_object_id) is None
        for field in fields:
            try:
                _ = field.value
            except ExternalStorageError:
                pass
            else:
                raise AssertionError('failed Python-root receiver retained SV storage')
        assert value.own_value.value == 1000 and value.local.value == 7
        value.own_value.value = 2000
        assert value.own_value.value == 2000
    svx.display('PYTHON_ROOT_OUTER_ROLLBACK_FIELDS_PASS')
    healthy = Derived(83)
    assert healthy.check(1) == 1184 and constructed_roots.count(healthy) == 1
    assert _native.inheritance_get(healthy._svx_remote_object_id) is healthy
    svx.close_instance(healthy)
    assert _native.inheritance_get(healthy._svx_remote_object_id) is None
    svx.display('PYTHON_ROOT_OUTER_ROLLBACK_RETRY_PASS')
    existing = Reinitialized(83)
    svx.publish_object('python_root_outer.existing', existing)
    existing.fail_again = True
    try:
        existing.__init__(83)
    except ValueError as error:
        assert str(error) == 'existing Python-root initializer failed'
    else:
        raise AssertionError('existing initializer failure returned normally')
    assert _native.inheritance_get(existing._svx_remote_object_id) is existing
    assert existing.count.value == 83 and existing.child_value.value == 100
    assert existing.check(1) == 1184
    svx.display('PYTHON_ROOT_OUTER_ROLLBACK_EXISTING_PASS')


@svx.export(name='python_root_outer.close_existing')
def close_existing():
    value = constructed_roots[-1]
    assert isinstance(value, Reinitialized)
    svx.close_instance(value)
    assert _native.inheritance_get(value._svx_remote_object_id) is None
