import svx
from svtypes import LogicValue
from svx_mirror.dpi_capabilities_pkg import (
    Mode, Pair, dpi_arrays, dpi_logic, dpi_mode, dpi_pair, dpi_scalar, dpi_task, dpi_text,
    sv_output, sv_task_output,
)


@svx.export(name='dpi_capabilities.run')
def run():
    doubled, total = svx.Output(), svx.Inout(10)
    assert dpi_scalar(7, doubled, total) == 8
    assert doubled.value == 14 and total.value == 17
    result = svx.Output()
    dpi_logic(LogicValue.from_string('10xz1010'), result)
    assert result.value == LogicValue.from_string('10xz1010')
    assert dpi_text('hello') == 'hello'
    mode = svx.Output()
    dpi_mode(Mode.ONE, mode)
    assert mode.value == Mode.ONE
    pair = Pair()
    pair.first.value = 21
    pair.second.value = 37
    pair_result = svx.Output()
    dpi_pair(pair, pair_result)
    assert pair_result.value.first.value == 21 and pair_result.value.second.value == 37
    result, total = svx.Output(), svx.Inout(10)
    assert dpi_task(7, result, total) is None
    assert result.value == 21 and total.value == 17
    changed = svx.Inout([10, 20, 30])
    dpi_arrays([1, 2, 3], changed)
    assert changed.value == [11, 22, 33]
    dpi_arrays([1, 2, 3], changed)
    assert changed.value == [12, 24, 36]
    empty = svx.Inout([])
    dpi_arrays([], empty)
    assert list(empty.value) == []
    svx.display('DPI_INPUT_INOUT_ARRAY_PASS')
    for count in (3, 0, 5):
        result = svx.Output()
        sv_output(count, result)
        assert list(result.value) == list(range(100, 100 + count))
        sv_task_output(count, result)
        assert list(result.value) == list(range(200, 200 + count))
    svx.display('SV_OUTPUT_DYNAMIC_ARRAY_PASS')
    svx.display('DPI_CAPABILITIES_PYTHON_PASS')
