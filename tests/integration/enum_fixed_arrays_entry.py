import svx
from svx_mirror.enum_fixed_arrays_pkg import Driver, first_t, second_t, wide_t, local_t


def integers(values):
    return [int(value) for value in values]


@svx.export(name='enum_fixed_arrays.run')
def run():
    assert first_t is not second_t, 'distinct enum declarations were merged'
    driver = Driver()
    size = driver.depth()
    assert integers(driver.first.value) == [0] * size
    assert integers(driver.second.value) == [3] * size
    driver.first[1].value = first_t.RUN
    driver.second[1].value = second_t.IDLE
    assert driver.first_at(1) == 1 and driver.second_at(1) == 0
    assert integers(driver.inherited_states.value) == [0, 3]
    driver.inherited_states[0].value = first_t.DONE
    assert integers(driver.inherited_states.value) == [3, 3]
    driver.wide[1].value = wide_t.HIGH
    assert integers(driver.wide.value) == [257, 257]
    driver.local_values[0].value = local_t.ACTIVE
    assert integers(driver.local_values.value) == [2, 2]
    driver.grid[1][0].value = second_t.DONE
    assert int(driver.grid[0][0].value) == 1 and int(driver.grid[1][0].value) == 3
    left = [first_t.RUN] * size
    right = [second_t.DONE] * size
    assert integers(driver.echo_first(left)) == [1] * size
    assert integers(driver.echo_second(right)) == [3] * size
    result, current = svx.Output(), svx.Inout([wide_t.LOW, wide_t.HIGH])
    driver.exchange(left, right, result, current)
    assert integers(result.value) == [0] + [3] * (size - 1)
    assert integers(current.value) == [511, 257]
    snapshot = driver.bundle.value
    assert integers(snapshot.first.value) == [0] * size
    assert integers(snapshot.second.value) == [3] * size
    snapshot.first[0].value = first_t.DONE
    snapshot.second[0].value = second_t.RUN
    returned = driver.echo_bundle(snapshot)
    assert integers(returned.first.value) == [3] + [0] * (size - 1)
    assert integers(returned.second.value) == [1] + [3] * (size - 1)
    driver.bundle.value = returned
    driver.bundle.wide[0].value = wide_t.LAST
    assert int(driver.bundle.wide[0].value) == 511
    assert driver.first_at(0) == 0 and driver.second_at(0) == 3
    svx.close_instance(driver)
    svx.display('ENUM_FIXED_ARRAYS_PYTHON_PASS')
