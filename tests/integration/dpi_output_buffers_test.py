import svx
from svx_mirror.dpi_output_buffers_pkg import fill, fill_task, fill_pair, ordinary


def expected(size):
    return [100 + size + index for index in range(size)]


@svx.export(name='dpi_output_buffers.run')
def run():
    for function in (fill, fill_task):
        for size in (7, 0, 1, 3, 1024, 0, 19):
            result = svx.Output([999] * size)
            assert function(result) is None
            assert result.value == expected(size)
        result = svx.Output()
        function(result)
        assert result.value == []
    left, right = svx.Output([0] * 2), svx.Output([0] * 11)
    fill_pair(left, right)
    assert left.value == expected(2) and right.value == expected(11)
    for result in (svx.Output(), svx.Output([0] * 17)):
        ordinary(result)
        assert result.value == [11, 22, 33]
    print('DPI_OUTPUT_BUFFERS_PYTHON_PASS', flush=True)
