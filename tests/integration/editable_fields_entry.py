import svx
from svx_mirror.editable_fields_pkg import Driver


@svx.export(name='editable_fields.run')
def run():
    driver = Driver()
    assert driver.count.value == 1
    driver.count.value = 9
    assert list(driver.values.value) == [10, 20, 30]
    driver.values.value[1] = 22
    history = driver.history.value
    history.append(3)
    assert history.pop(0) == 1
    dynamic = driver.dynamic_values.value
    dynamic.append(6)
    driver.mapping.value[7] = 77
    assert driver.native_values_match()
    svx.display('EDITABLE_FIELDS_PYTHON_PASS')
