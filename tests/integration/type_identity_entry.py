import svx
from svx_mirror.type_identity_pkg import Driver


@svx.export(name='type_identity.run')
def run():
    value = Driver(11)
    assert value.code() == 65535 and value.negative() == -1
    assert value.same(value.self_ref())
    for index, name in enumerate(('data', 'data_type', 'data_read', 'data_write')):
        assert getattr(value, name).value == 11 + index
        getattr(value, name).value = 30 + index
    for index, name in enumerate(('data', 'data_type', 'data_read', 'data_write')):
        assert getattr(value, name).value == 30 + index
    count, result = svx.Inout(3), svx.Output()
    value.exchange([1, 2], 9, count, result)
    assert count.value == 5 and result.value == 14
    svx.close_instance(value)
    svx.display('TYPE_IDENTITY_PYTHON_PASS')
