import svx
from svx_mirror.nested_struct_ref_pkg import Driver


@svx.export(name='nested_struct_ref.run')
def run():
    driver = Driver()
    value = driver.read()
    assert driver.valid(value)
    assert value.queues.value[0][0].object_number != 0
    svx.display('NESTED_STRUCT_REF_PYTHON_PASS')
