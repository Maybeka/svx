import svx
from svx import _native
from svtypes import ExternalStorageError
from tests.integration.sv_root_target_derived import D

failed = []


class Failed(D):
    def __init__(self):
        super().__init__()
        assert self.check() == 1135
        failed.append((self, self.count, self.retry, self.extra))
        svx.publish_object('outer_initializer.failed', self)
        raise ValueError('outer Python initializer failed after complete C')


@svx.export(name='outer_initializer.run')
def run():
    for _ in range(2):
        try:
            Failed()
        except ValueError as error:
            assert str(error) == 'outer Python initializer failed after complete C'
        else:
            raise AssertionError('failed outer initializer returned normally')
    assert len({entry[0]._svx_remote_object_id for entry in failed}) == 2
    for value, *fields in failed:
        assert _native.inheritance_get(value._svx_remote_object_id) is None, 'failed receiver still bound'
        for field in fields:
            try:
                _ = field.value
            except ExternalStorageError:
                pass
            else:
                raise AssertionError('failed receiver retained live SV field storage')
        assert value.own.value == 1000
        value.own.value = 2000
        assert value.own.value == 2000
    svx.display('OUTER_INITIALIZER_ROLLBACK_PYTHON_PASS')
    healthy = D()
    assert healthy.check() == 1135
    assert _native.inheritance_get(healthy._svx_remote_object_id) is healthy
    svx.close_instance(healthy)
    assert _native.inheritance_get(healthy._svx_remote_object_id) is None
    svx.display('OUTER_INITIALIZER_ROLLBACK_RETRY_PASS')
