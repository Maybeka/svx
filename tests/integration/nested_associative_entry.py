import svx
from svtypes import ExternalStorageError
from svx.inheritance import close_instance
from svx_mirror.nested_associative_pkg import Driver


@svx.export(name='nested_associative.run')
def run():
    owner = Driver()
    try:
        assert owner.values[1][2].value == 12
        owner.values[1][2].value = 19
        owner.values[1].value[8] = 18
        del owner.values[1].value[3]
        assert owner.values[1].value.pop(2) == 19
        owner.values.value[7] = {8: 78}
        assert owner.values[7][8].value == 78
        for operation in ('read', 'write', 'delete'):
            try:
                if operation == 'read':
                    _ = owner.values[99][1].value
                elif operation == 'write':
                    owner.values[99][1].value = 991
                else:
                    del owner.values[99].value[1]
            except ExternalStorageError as error:
                assert 'missing associative field key' in str(error.__cause__)
            else:
                raise AssertionError(f'missing intermediate key unexpectedly accepted for {operation}')
        assert owner.check()
    finally:
        close_instance(owner._svx_remote_object_id)
    svx.display('NESTED_ASSOCIATIVE_PYTHON_PASS')
