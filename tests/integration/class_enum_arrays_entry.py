import svx
from svx_mirror.class_enum_arrays_pkg import Driver


@svx.export(name='class_enum_arrays.run')
def run():
    first_t, second_t = Driver.first_t, Driver.second_t
    assert first_t is not second_t
    driver = Driver()
    assert [int(item) for item in driver.first.value] == [0, 0, 0]
    assert [int(item) for item in driver.second.value] == [5, 5, 5]
    driver.first[1].value = first_t.A_RUN
    driver.second[1].value = second_t.B_RUN
    assert driver.first_at(1) == 1 and driver.second_at(1) == 2
    driver.first.value = [first_t.A_DONE, first_t.A_RUN, first_t.A_IDLE]
    driver.second.value = [second_t.B_IDLE, second_t.B_RUN, second_t.B_DONE]
    assert driver.first_at(0) == 4 and driver.second_at(0) == 0
    a, b = svx.Output(), svx.Output()
    driver.get_values(a, b)
    assert [int(item) for item in a.value] == [4, 1, 0]
    assert [int(item) for item in b.value] == [0, 2, 5]
    driver.set_values([first_t.A_RUN] * 3, [second_t.B_RUN] * 3)
    assert [int(item) for item in driver.first.value] == [1, 1, 1]
    assert [int(item) for item in driver.second.value] == [2, 2, 2]
    svx.close_instance(driver)
    svx.display('CLASS_ENUM_ARRAYS_PYTHON_PASS')
