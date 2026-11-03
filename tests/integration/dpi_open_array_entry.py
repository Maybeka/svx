import svx
from svx_mirror.dpi_open_array_pkg import dpi_sum


@svx.export(name='dpi_open_array.run')
def run():
    assert dpi_sum([1, 7, 31]) == 39
    assert dpi_sum([]) == 0
    svx.display('DPI_OPEN_ARRAY_PYTHON_PASS')
